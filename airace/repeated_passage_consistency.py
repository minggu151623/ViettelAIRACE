"""Exact repeated-passage consistency graph for preregistered H40."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .multiview_consensus import (EXPECTED_VIEW_SHA256, H34_PATH, VIEW_DIRS,
                                  _load_baseline, _load_views, frozen_digest)
from .normalize import normalize_key
from .phrase_verifier import KNOWN_HAZARDS


EXPECTED_INPUT_SHA256 = "d68702073a5e478df60ab389b71587813ffac08475902f043446346ef0f15bcf"
EXPECTED_BASELINE_SHA256 = "a9b9ae07997e57080ed8ce2ad9c390f4cd8c229e8eae8de447f6f47ae6ff4d0b"
SOURCE_FAMILY = {
    "bami_v15": "bami", "bami_v3": "bami", "vietmed": "vietmed",
    "qwen_guarded": "qwen_guarded", "h34_oof": "h34_oof",
}
CANDIDATE_TYPES = {"CHẨN_ĐOÁN", "THUỐC"}


@dataclass(frozen=True, order=True)
class Occurrence:
    record: int
    start: int
    end: int


@dataclass(frozen=True, order=True)
class RelativeEntity:
    start: int
    end: int
    type: str

    @property
    def length(self) -> int:
        return self.end - self.start


def verify_hashes(input_dir: Path, baseline_zip: Path) -> dict[str, str]:
    observed = {name: frozen_digest(path) for name, path in VIEW_DIRS.items()}
    observed["h34_oof"] = frozen_digest(H34_PATH)
    observed["input_tree"] = frozen_digest(input_dir)
    observed["baseline_zip"] = hashlib.sha256(baseline_zip.read_bytes()).hexdigest()
    expected = {**EXPECTED_VIEW_SHA256, "input_tree": EXPECTED_INPUT_SHA256,
                "baseline_zip": EXPECTED_BASELINE_SHA256}
    mismatch = {name: {"expected": expected[name], "observed": value}
                for name, value in observed.items() if value != expected[name]}
    if mismatch:
        raise ValueError(f"H40 frozen source mismatch: {json.dumps(mismatch, sort_keys=True)}")
    return observed


def repeated_lines(input_dir: Path, minimum: int = 40) -> dict[str, list[Occurrence]]:
    groups: dict[str, list[Occurrence]] = defaultdict(list)
    for path in sorted(input_dir.glob("*.txt"), key=lambda value: int(value.stem)):
        record = int(path.stem)
        raw = path.read_text(encoding="utf-8")
        for match in re.finditer(r"[^\n]+", raw):
            untrimmed = match.group()
            text = untrimmed.strip()
            if len(text) < minimum:
                continue
            start = match.start() + len(untrimmed) - len(untrimmed.lstrip())
            groups[text].append(Occurrence(record, start, start + len(text)))
    return {text: values for text, values in groups.items()
            if len({value.record for value in values}) >= 2}


def _view_rows() -> dict[str, dict[int, list[tuple[int, int, str]]]]:
    views, _ = _load_views()
    result: dict[str, dict[int, list[tuple[int, int, str]]]] = {}
    for source, keys in views.items():
        records: dict[int, list[tuple[int, int, str]]] = defaultdict(list)
        for record, start, end, kind in keys:
            records[record].append((start, end, kind))
        result[source] = records
    return result


def collect_evidence(occurrences: list[Occurrence], views: dict[str, dict[int, list[tuple[int, int, str]]]],
                     excluded: Occurrence | None = None) -> dict[RelativeEntity, dict[str, set[Any]]]:
    evidence: dict[RelativeEntity, dict[str, set[Any]]] = defaultdict(
        lambda: {"occurrences": set(), "families": set(), "units": set()})
    for occurrence in occurrences:
        if occurrence == excluded:
            continue
        for source, records in views.items():
            family = SOURCE_FAMILY[source]
            for start, end, kind in records.get(occurrence.record, []):
                if occurrence.start <= start and end <= occurrence.end:
                    entity = RelativeEntity(start - occurrence.start, end - occurrence.start, kind)
                    evidence[entity]["occurrences"].add(occurrence)
                    evidence[entity]["families"].add(family)
                    evidence[entity]["units"].add((family, occurrence))
    return evidence


def entity_rank(entity: RelativeEntity, evidence: dict[str, set[Any]]) -> tuple[int, int, int, int]:
    return (len({item.record for item in evidence["occurrences"]}), len(evidence["families"]),
            len(evidence["units"]), -entity.length)


def _is_hazard(text: str, entity: RelativeEntity) -> bool:
    mention = text[entity.start:entity.end]
    if normalize_key(mention) in KNOWN_HAZARDS:
        return True
    stripped = mention.strip()
    return (entity.type == "TRIỆU_CHỨNG" and bool(stripped) and stripped[0].isdigit()
            and not any(char.isalpha() for char in stripped.replace("°C", "")))


def eligible_entities(text: str, occurrences: list[Occurrence],
                      evidence: dict[RelativeEntity, dict[str, set[Any]]]) -> tuple[list[RelativeEntity], int]:
    threshold = math.ceil(len({value.record for value in occurrences}) / 2)
    eligible = [entity for entity, support in evidence.items()
                if len({item.record for item in support["occurrences"]}) >= max(2, threshold)
                and len(support["families"]) >= 2 and not _is_hazard(text, entity)]
    excluded_ties: set[RelativeEntity] = set()
    by_position: dict[tuple[int, int], list[RelativeEntity]] = defaultdict(list)
    for entity in eligible:
        by_position[(entity.start, entity.end)].append(entity)
    for values in by_position.values():
        if len(values) < 2:
            continue
        ranks = {entity: entity_rank(entity, evidence[entity]) for entity in values}
        best = max(ranks.values())
        winners = [entity for entity, rank in ranks.items() if rank == best]
        if len(winners) > 1:
            excluded_ties.update(winners)
    return [entity for entity in eligible if entity not in excluded_ties], len(excluded_ties)


def select_non_overlapping(text: str, entities: list[RelativeEntity],
                           evidence: dict[RelativeEntity, dict[str, set[Any]]]) -> list[RelativeEntity]:
    """Weighted interval scheduling with deterministic lexicographic ties."""
    ordered = sorted(entities, key=lambda item: (item.end, item.start, item.type))
    previous = []
    for index, entity in enumerate(ordered):
        prior = index - 1
        while prior >= 0 and ordered[prior].end > entity.start:
            prior -= 1
        previous.append(prior)

    def utility(entity: RelativeEntity) -> int:
        rank = entity_rank(entity, evidence[entity])
        return rank[0] * 10**9 + rank[1] * 10**6 + rank[2] * 10**3 + 1000 + rank[3]

    best: list[tuple[int, tuple[RelativeEntity, ...]]] = [(0, ())]
    for index, entity in enumerate(ordered):
        without = best[index]
        base_score, base_entities = best[previous[index] + 1]
        with_entity = (base_score + utility(entity), base_entities + (entity,))
        if with_entity[0] > without[0] or (with_entity[0] == without[0] and with_entity[1] < without[1]):
            best.append(with_entity)
        else:
            best.append(without)
    return sorted(best[-1][1])


def canonical(text: str, occurrences: list[Occurrence], views: dict[str, dict[int, list[tuple[int, int, str]]]],
              excluded: Occurrence | None = None) -> tuple[list[RelativeEntity], int]:
    evidence = collect_evidence(occurrences, views, excluded)
    eligible, ties = eligible_entities(text, [value for value in occurrences if value != excluded], evidence)
    return select_non_overlapping(text, eligible, evidence), ties


def signature(rows: list[dict[str, Any]], occurrence: Occurrence) -> set[RelativeEntity]:
    return {RelativeEntity(row["position"][0] - occurrence.start,
                           row["position"][1] - occurrence.start, row["type"])
            for row in rows if occurrence.start <= row["position"][0]
            and row["position"][1] <= occurrence.end}


def run_early_gates(input_dir: Path, baseline_dir: Path, baseline_zip: Path,
                    review_path: Path) -> dict[str, Any]:
    hashes = verify_hashes(input_dir, baseline_zip)
    groups = repeated_lines(input_dir)
    views = _view_rows()
    baseline, _ = _load_baseline(baseline_dir)
    canonicals: dict[str, list[RelativeEntity]] = {}
    tie_count = 0
    stability_total = stability_equal = 0
    changed_rows = 0
    affected_groups = 0
    for text, occurrences in groups.items():
        selected, ties = canonical(text, occurrences, views)
        canonicals[text] = selected
        tie_count += ties
        if len({value.record for value in occurrences}) >= 3:
            for occurrence in occurrences:
                reduced, _ = canonical(text, occurrences, views, occurrence)
                stability_total += 1
                stability_equal += reduced == selected
        differences = 0
        for occurrence in occurrences:
            current = signature(baseline[occurrence.record], occurrence)
            differences += len(current.symmetric_difference(set(selected)))
        if differences:
            affected_groups += 1
            changed_rows += differences

    review = json.loads(review_path.read_text(encoding="utf-8"))["rows"]
    positives = [row for row in review if row["group"] == "positive_control"]
    retained = 0
    for row in positives:
        present = True
        for text, occurrences in groups.items():
            for occurrence in occurrences:
                if (occurrence.record == row["record"] and occurrence.start <= row["position"][0]
                        and row["position"][1] <= occurrence.end):
                    relative = RelativeEntity(row["position"][0] - occurrence.start,
                                              row["position"][1] - occurrence.start, row["type"])
                    present = relative in canonicals[text]
        retained += present
    retention = retained / max(1, len(positives))
    stability = stability_equal / max(1, stability_total)
    gates = {
        "frozen_hashes_match": True,
        "leave_one_occurrence_out_stability_at_least_0_95": stability >= 0.95,
        "positive_control_retention_at_least_0_95": retention >= 0.95,
        "registered_and_numeric_hazards_excluded": True,
        "no_cross_type_tie_integrated": True,
        "changed_rows_between_100_and_400": 100 <= changed_rows <= 400,
    }
    return {"status": "early_gates_passed" if all(gates.values()) else "failed_before_integration",
            "frozen_hashes": hashes,
            "census": {"duplicate_groups": len(groups),
                       "occurrences": sum(len(values) for values in groups.values()),
                       "records_covered": len({item.record for values in groups.values() for item in values}),
                       "affected_groups": affected_groups,
                       "canonical_entities": sum(len(values) for values in canonicals.values()),
                       "excluded_cross_type_ties": tie_count,
                       "proposed_changed_rows": changed_rows},
            "leave_one_occurrence_out": {"equal": stability_equal, "total": stability_total,
                                         "stability": stability},
            "positive_controls": {"retained": retained, "total": len(positives), "rate": retention},
            "gates": gates}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("turn2/input"))
    parser.add_argument("--baseline", type=Path, default=Path("turn2/output_v10_multiview_consensus"))
    parser.add_argument("--baseline-zip", type=Path, default=Path("turn2/output_v10_multiview_consensus.zip"))
    parser.add_argument("--review", type=Path, default=Path("experiments/H38_multiview_consensus/results/review.json"))
    parser.add_argument("--output", type=Path, default=Path("experiments/H40_repeated_passage_consistency/results/early_gates.json"))
    args = parser.parse_args()
    report = run_early_gates(args.input, args.baseline, args.baseline_zip, args.review)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
