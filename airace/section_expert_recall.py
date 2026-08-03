"""H58 boundary-aware high-recall fusion over the frozen H57 proposal bank."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .assertions import infer_assertions
from .multiview_consensus import overlap, relation
from .normalize import normalize_key
from .package_output import package_output
from .phrase_verifier import KNOWN_HAZARDS
from .schema import CANDIDATE_TYPES, Entity
from .section_expert_core import (BASELINE_SHA256, _aliases, _load_records,
                                  _neural_support, frozen_digest)
from .validator import validate_output_dir


CLINICAL_TYPES = {"CHẨN_ĐOÁN", "TRIỆU_CHỨNG"}
MEASUREMENT = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:°?c|mmhg|lần/phút|%|ml(?:/24h)?|mg|g|mmol|cm|cc)\b",
    re.IGNORECASE,
)


def unsupported_row_allowed(row: dict[str, Any]) -> bool:
    """Frozen H58 type router for Qwen-only disjoint proposals."""
    if normalize_key(row["text"]) in KNOWN_HAZARDS:
        return False
    if row["type"] in CLINICAL_TYPES:
        return any(char.isalpha() for char in row["text"])
    return row["type"] == "KẾT_QUẢ_XÉT_NGHIỆM" and bool(MEASUREMENT.search(row["text"]))


def _candidate_value(row: dict[str, Any], aliases: dict[tuple[str, str], set[tuple[str, ...]]]) -> list[str]:
    if row["type"] not in CANDIDATE_TYPES:
        return []
    values = aliases.get((row["type"], normalize_key(row["text"])), set())
    return list(next(iter(values))) if len(values) == 1 else []


def _select(input_dir: Path, baseline: dict[int, list[dict[str, Any]]],
            proposal_dir: Path) -> tuple[list[dict[str, Any]], Counter[str]]:
    neural = _neural_support()
    aliases = _aliases(baseline)
    selected: list[dict[str, Any]] = []
    rejected: Counter[str] = Counter()
    for path in sorted(proposal_dir.glob("*.json"), key=lambda value: int(value.stem)):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if artifact.get("chunks_complete") != artifact.get("chunks_expected"):
            raise ValueError(f"incomplete H57 proposal record: {path}")
        record = int(path.stem)
        for row in artifact["entities"]:
            support = sorted(neural.get((record, *row["position"], row["type"]), set()))
            rel, hits = relation(row, baseline[record])
            if rel == "contained_same_type" and hits:
                # Exact equality is classified as contained by the shared helper;
                # H58 changes only a genuinely shorter boundary.
                if not support or not all(
                    len(row["text"]) < len(baseline[record][index]["text"])
                    for index in hits
                ):
                    rejected["exact_or_unsupported_contained"] += 1
                    continue
                mode = "supported_shorter_boundary"
            elif rel == "disjoint":
                if support:
                    mode = "supported_disjoint"
                elif unsupported_row_allowed(row):
                    mode = "qwen_only_clinical_or_numeric"
                else:
                    rejected["unsupported_type_router"] += 1
                    continue
            else:
                rejected[rel] += 1
                continue
            value = {"record": record, **row, "mode": mode,
                     "baseline_overlap_indices": hits,
                     "independent_sources": support}
            value["candidates"] = _candidate_value(row, aliases) if support else []
            selected.append(value)

    # If Qwen emits competing types on an identical/overlapping unsupported
    # region, abstain on that region instead of inventing a type tie-breaker.
    ambiguous: set[int] = set()
    for left_index, left in enumerate(selected):
        for right_index in range(left_index + 1, len(selected)):
            right = selected[right_index]
            if left["record"] != right["record"]:
                continue
            if not overlap(tuple(left["position"]), tuple(right["position"])):
                continue
            if left["mode"] == "qwen_only_clinical_or_numeric" and right["mode"] == left["mode"]:
                ambiguous.update((left_index, right_index))
    candidates = [row for index, row in enumerate(selected) if index not in ambiguous]
    rejected["ambiguous_qwen_only_overlap"] += len(ambiguous)

    kept: list[dict[str, Any]] = []
    for row in sorted(candidates, key=lambda value: (
        -len(value["independent_sources"]),
        -(value["position"][1] - value["position"][0]),
        value["record"], value["position"][0], value["type"],
    )):
        if any(row["record"] == old["record"] and
               overlap(tuple(row["position"]), tuple(old["position"])) for old in kept):
            rejected["selected_overlap"] += 1
            continue
        kept.append(row)
    kept.sort(key=lambda value: (value["record"], *value["position"], value["type"]))
    return kept, rejected


def build(input_dir: Path, baseline_dir: Path, baseline_zip: Path,
          proposal_dir: Path, output_dir: Path, zip_path: Path) -> dict[str, Any]:
    observed = hashlib.sha256(baseline_zip.read_bytes()).hexdigest()
    if observed != BASELINE_SHA256:
        raise ValueError(f"H58 baseline hash mismatch: {observed}")
    baseline = _load_records(baseline_dir)
    selected, rejected = _select(input_dir, baseline, proposal_dir)
    by_record: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        by_record[row["record"]].append(row)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    removed = additions = 0
    for record in range(1, 101):
        raw = (input_dir / f"{record}.txt").read_text(encoding="utf-8")
        rows = [dict(row) for row in baseline[record]]
        remove: set[int] = set()
        new_rows: list[dict[str, Any]] = []
        for proposal in by_record[record]:
            hits = proposal["baseline_overlap_indices"]
            if proposal["mode"] == "supported_shorter_boundary":
                remove.update(hits)
                assertions = list(dict.fromkeys(
                    item for index in hits for item in rows[index].get("assertions", [])
                ))
                candidates = list(dict.fromkeys(
                    item for index in hits for item in rows[index].get("candidates", [])
                ))
                removed += len(hits)
            else:
                assertions = list(infer_assertions(
                    Entity(text=proposal["text"], type=proposal["type"],
                           position=tuple(proposal["position"])), raw
                ))
                candidates = proposal["candidates"]
                additions += 1
            entity = Entity(
                text=proposal["text"], type=proposal["type"],
                position=tuple(proposal["position"]), assertions=assertions,
                candidates=candidates if proposal["type"] in CANDIDATE_TYPES else None,
            )
            new_rows.append(entity.to_dict())
        merged = [row for index, row in enumerate(rows) if index not in remove] + new_rows
        merged.sort(key=lambda row: (*row["position"], row["type"], row["text"]))
        (output_dir / f"{record}.json").write_text(
            json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    validation = validate_output_dir(input_dir, output_dir, position_mode="raw")
    modes = Counter(row["mode"] for row in selected)
    gates = {
        "baseline_hash_matches": True,
        "proposal_bank_complete": len(list(proposal_dir.glob("*.json"))) == 100,
        "at_least_150_semantic_changes": removed + additions >= 150,
        "qwen_only_changes_at_most_200": modes["qwen_only_clinical_or_numeric"] <= 200,
        "no_new_nonempty_candidate_codes": all(
            not row["candidates"] or row["independent_sources"]
            for row in selected if row["type"] in CANDIDATE_TYPES
        ),
        "all_records_validate": validation["ok"],
    }
    report: dict[str, Any] = {
        "hypothesis": "H58_section_expert_recall", "proposal_digest": frozen_digest(proposal_dir),
        "selected": len(selected), "removed_baseline_rows": removed,
        "added_rows": additions, "semantic_changes": removed + additions,
        "selected_modes": dict(modes), "selected_types": dict(Counter(row["type"] for row in selected)),
        "rejected": dict(rejected), "validation": validation, "gates": gates,
        "selected_rows": selected, "decision": "PASS" if all(gates.values()) else "FAIL",
    }
    if report["decision"] == "PASS":
        package_output(output_dir, zip_path)
        first = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        repeat = zip_path.with_name(zip_path.stem + "_repeat.zip")
        package_output(output_dir, repeat)
        second = hashlib.sha256(repeat.read_bytes()).hexdigest()
        repeat.unlink()
        report["zip_sha256"] = first
        report["repeat_zip_sha256"] = second
        report["byte_identical_repeat"] = first == second
        if first != second:
            zip_path.unlink()
            report["decision"] = "FAIL"
    elif zip_path.exists():
        zip_path.unlink()
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("turn2/input"))
    parser.add_argument("--baseline", type=Path, default=Path("turn2/output_v10_multiview_consensus"))
    parser.add_argument("--baseline-zip", type=Path, default=Path("turn2/output_v10_multiview_consensus.zip"))
    parser.add_argument("--proposals", type=Path, default=Path("experiments/H57_section_expert_core/proposals"))
    parser.add_argument("--output", type=Path, default=Path("turn2/output_v14_section_expert_recall"))
    parser.add_argument("--zip", type=Path, default=Path("turn2/output_v14_section_expert_recall.zip"))
    parser.add_argument("--report", type=Path, default=Path("experiments/H58_section_expert_recall/results/report.json"))
    args = parser.parse_args()
    report = build(args.input, args.baseline, args.baseline_zip, args.proposals, args.output, args.zip)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "selected_rows"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
