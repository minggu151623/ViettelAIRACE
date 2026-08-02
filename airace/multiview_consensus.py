"""Large-scale exact multi-view consensus with frozen verification gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .assertions import infer_assertions
from .controlled_novel_verifier import _review_rows
from .normalize import normalize_key
from .package_output import package_output
from .phrase_verifier import KNOWN_HAZARDS
from .schema import Entity
from .validator import validate_output_dir


VIEW_DIRS = {
    "bami_v15": Path("experiments/H_turn2_multimodel_core/proposals_bami_v15"),
    "bami_v3": Path("experiments/H_turn2_multimodel_core/proposals_bami_v3"),
    "vietmed": Path("experiments/H_turn2_multimodel_core/proposals_vietmed"),
    "qwen_guarded": Path("experiments/H_turn2_llm_guarded_rebuild/output_entity_ablation"),
}
H34_PATH = Path("experiments/H34_minimum_epoch_recovery/results/combined_oof_predictions.json")
CONTROL_TYPES = ("CHẨN_ĐOÁN", "TRIỆU_CHỨNG", "TÊN_XÉT_NGHIỆM", "THUỐC")
EXPECTED_BASELINE_ZIP_SHA256 = "032041a8f92bc97ca6a92d4cb4809d6aa39122471056df97bfe1fd1fe4585abc"
EXPECTED_VIEW_SHA256 = {
    "bami_v15": "2dd6b6e6804e80afb3419f32c705851b4ae8055e4aa866492644c444958091cd",
    "bami_v3": "71d6a38f7f55aad80857e456172e9c00175d6c47cf9f9cf4cf8498fbd116a75e",
    "vietmed": "5bc85a01d47119d29696865d3be0feb51d905c3eecd1780f9d4802bb86c3b69b",
    "qwen_guarded": "0f5a53fdd46a82dc2556ae11f3b53615a5ed6448cc156100801aac2c8bc979c4",
    "h34_oof": "21823c984a992ce29ac6dc84e529e3056ec4192db0b23137d2bdcc82cce811a4",
}


def frozen_digest(path: Path) -> str:
    """Hash a frozen file/tree including stable relative names and delimiters."""
    digest = hashlib.sha256()
    files = [path] if path.is_file() else sorted(item for item in path.rglob("*") if item.is_file())
    for item in files:
        name = item.name if path.is_file() else str(item.relative_to(path))
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def verify_frozen_sources(baseline_zip: Path) -> dict[str, str]:
    observed = {name: frozen_digest(path) for name, path in VIEW_DIRS.items()}
    observed["h34_oof"] = frozen_digest(H34_PATH)
    observed["baseline_zip"] = hashlib.sha256(baseline_zip.read_bytes()).hexdigest()
    expected = {**EXPECTED_VIEW_SHA256, "baseline_zip": EXPECTED_BASELINE_ZIP_SHA256}
    mismatches = {name: {"expected": expected[name], "observed": value}
                  for name, value in observed.items() if value != expected[name]}
    if mismatches:
        raise ValueError(f"Frozen H38 source hash mismatch: {json.dumps(mismatches, sort_keys=True)}")
    return observed


def exact_key(record: int, row: dict[str, Any]) -> tuple[int, int, int, str]:
    return (record, int(row["position"][0]), int(row["position"][1]), str(row["type"]))


def overlap(left: tuple[int, int], right: tuple[int, int]) -> bool:
    return max(left[0], right[0]) < min(left[1], right[1])


def relation(row: dict[str, Any], baseline: list[dict[str, Any]]) -> tuple[str, list[int]]:
    position = tuple(row["position"])
    hits = [index for index, base in enumerate(baseline)
            if overlap(position, tuple(base["position"]))]
    if not hits:
        return "disjoint", hits
    values = [baseline[index] for index in hits]
    if all(base["type"] == row["type"] and
           base["position"][0] <= position[0] and position[1] <= base["position"][1]
           for base in values):
        return "contained_same_type", hits
    if all(base["type"] == row["type"] and
           position[0] <= base["position"][0] and base["position"][1] <= position[1]
           for base in values):
        return "contains_same_type", hits
    if any(base["type"] != row["type"] for base in values):
        return "cross_type", hits
    return "partial_same_type", hits


def _load_views() -> tuple[dict[str, set[tuple[int, int, int, str]]], dict[tuple[int, int, int, str], dict[str, Any]]]:
    views: dict[str, set[tuple[int, int, int, str]]] = {}
    representative: dict[tuple[int, int, int, str], dict[str, Any]] = {}
    for name, root in VIEW_DIRS.items():
        keys = set()
        for path in root.glob("*.json"):
            record = int(path.stem)
            for row in json.loads(path.read_text(encoding="utf-8")):
                key = exact_key(record, row)
                keys.add(key)
                representative.setdefault(key, row)
        views[name] = keys
    keys = set()
    for row in json.loads(H34_PATH.read_text(encoding="utf-8")):
        record = int(row["record"])
        key = exact_key(record, row)
        keys.add(key)
        representative.setdefault(key, row)
    views["h34_oof"] = keys
    return views, representative


def _load_baseline(root: Path) -> tuple[dict[int, list[dict[str, Any]]], set[tuple[int, int, int, str]]]:
    records = {}
    keys = set()
    for path in root.glob("*.json"):
        record = int(path.stem)
        rows = json.loads(path.read_text(encoding="utf-8"))
        records[record] = rows
        keys.update(exact_key(record, row) for row in rows)
    return records, keys


def collect_review_rows(input_dir: str | Path, baseline_dir: str | Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    inputs, baseline_root = Path(input_dir), Path(baseline_dir)
    baseline, baseline_keys = _load_baseline(baseline_root)
    views, representative = _load_views()
    union = set().union(*views.values())

    rows = []
    relation_counts: Counter[str] = Counter()
    candidate_rows = []
    for key in sorted(union - baseline_keys):
        support = [name for name, values in views.items() if key in values]
        if len(support) < 3:
            continue
        record, start, end, kind = key
        raw = (inputs / f"{record}.txt").read_text(encoding="utf-8")
        row = {"record": record, "position": [start, end], "text": raw[start:end],
               "type": kind, "record_support": len(support), "sources": support,
               "confidence": max(float(representative[key].get("confidence", 0.0)), 0.0)}
        rel, hits = relation(row, baseline[record])
        relation_counts[rel] += 1
        if rel not in {"disjoint", "contained_same_type"}:
            continue
        row["relation"] = rel
        row["baseline_overlap_indices"] = hits
        candidate_rows.append(row)

    # Deterministic H37-present positive controls, stratified by type.
    control_pool: dict[str, list[tuple[int, int, int, str]]] = defaultdict(list)
    for key in baseline_keys:
        support = sum(key in values for values in views.values())
        if support >= 3 and key[3] in CONTROL_TYPES:
            control_pool[key[3]].append(key)
    controls = []
    for kind in CONTROL_TYPES:
        ranked = sorted(control_pool[kind], key=lambda key: hashlib.sha256(
            f"3817:{key}".encode()).hexdigest())[:12]
        for record, start, end, _ in ranked:
            raw = (inputs / f"{record}.txt").read_text(encoding="utf-8")
            controls.append({"record": record, "position": [start, end],
                             "text": raw[start:end], "type": kind,
                             "record_support": sum((record, start, end, kind) in values
                                                   for values in views.values()),
                             "confidence": 1.0})

    # Explicit hazards are controls even when structural rules already exclude them.
    hazards = []
    for key in sorted(union):
        record, start, end, kind = key
        raw = (inputs / f"{record}.txt").read_text(encoding="utf-8")
        if normalize_key(raw[start:end]) in KNOWN_HAZARDS:
            hazards.append({"record": record, "position": [start, end],
                            "text": raw[start:end], "type": kind,
                            "record_support": sum(key in values for values in views.values()),
                            "confidence": 0.0})

    for group, values in (("novel", candidate_rows), ("positive_control", controls),
                          ("negative_control", hazards)):
        for value in values:
            record, (start, end) = value["record"], value["position"]
            raw = (inputs / f"{record}.txt").read_text(encoding="utf-8")
            rows.append({"id": len(rows), "group": group, **value,
                         "expected": "KEEP" if group == "positive_control" else
                                     "DROP" if group == "negative_control" else None,
                         "context": raw[max(0, start - 180):start] + "⟦" + raw[start:end] + "⟧" + raw[end:min(len(raw), end + 180)]})
    census = {"exact_novel_three_view": sum(
                  key not in baseline_keys and sum(key in value for value in views.values()) >= 3
                  for key in union),
              "structurally_actionable": len(candidate_rows),
              "relation_counts": dict(relation_counts),
              "positive_controls": len(controls), "negative_controls": len(hazards)}
    return rows, census


def _candidate_aliases(baseline: dict[int, list[dict[str, Any]]]) -> dict[tuple[str, str], set[tuple[str, ...]]]:
    aliases: dict[tuple[str, str], set[tuple[str, ...]]] = defaultdict(set)
    for values in baseline.values():
        for row in values:
            if row["type"] in {"CHẨN_ĐOÁN", "THUỐC"}:
                aliases[(row["type"], normalize_key(row["text"]))].add(
                    tuple(row.get("candidates") or []))
    return aliases


def _remove_new_overlaps(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = []
    ranked = sorted(rows, key=lambda row: (-row["record_support"],
                    -(row["position"][1] - row["position"][0]), row["record"],
                    row["position"][0], row["position"][1], row["type"]))
    for row in ranked:
        if any(row["record"] == old["record"] and
               overlap(tuple(row["position"]), tuple(old["position"])) for old in selected):
            continue
        selected.append(row)
    return sorted(selected, key=lambda row: (row["record"], *row["position"], row["type"]))


def run_experiment(input_dir: str | Path, baseline_dir: str | Path,
                   output_dir: str | Path, zip_path: str | Path,
                   results_dir: str | Path,
                   baseline_zip: str | Path = "turn2/output_v9_verified_symptoms.zip") -> dict[str, Any]:
    inputs, baseline_root = Path(input_dir), Path(baseline_dir)
    output, results = Path(output_dir), Path(results_dir)
    frozen_hashes = verify_frozen_sources(Path(baseline_zip))
    results.mkdir(parents=True, exist_ok=True)
    review_rows, census = collect_review_rows(inputs, baseline_root)
    review = _review_rows(review_rows, results / "review.json", batch_size=18)
    reviewed = review["rows"]
    positives = [row for row in reviewed if row["group"] == "positive_control"]
    negatives = [row for row in reviewed if row["group"] == "negative_control"]
    novel = [row for row in reviewed if row["group"] == "novel"]
    complete = all(row["semantic"] is not None and row["boundary"] is not None for row in reviewed)
    agreement = sum(row["semantic"] is not None and row["boundary"] is not None and
                    row["semantic"]["action"] == row["boundary"]["action"]
                    for row in reviewed) / max(1, len(reviewed))
    retention = sum(row["accepted"] for row in positives) / max(1, len(positives))
    hazard_drop = sum(not row["accepted"] for row in negatives) / max(1, len(negatives))

    baseline, _ = _load_baseline(baseline_root)
    aliases = _candidate_aliases(baseline)
    accepted = []
    candidate_skips = []
    for row in novel:
        if not row["accepted"]:
            continue
        if row["relation"] == "disjoint" and row["type"] in {"CHẨN_ĐOÁN", "THUỐC"}:
            choices = aliases.get((row["type"], normalize_key(row["text"])), set())
            if len(choices) != 1 or not next(iter(choices), ()):
                candidate_skips.append(row)
                continue
            row["alias_candidates"] = list(next(iter(choices)))
        accepted.append(row)
    accepted = _remove_new_overlaps(accepted)

    gates = {
        "frozen_hashes_match": True,
        "verifier_responses_complete": complete,
        "positive_control_retention_at_least_0_85": retention >= 0.85,
        "registered_hazard_drop_rate_equals_1": hazard_drop == 1.0,
        "prompt_action_agreement_at_least_0_80": agreement >= 0.80,
        "at_least_150_rows_survive_all_filters": len(accepted) >= 150,
    }
    report: dict[str, Any] = {"census": census, "positive_control_retention": retention,
        "frozen_hashes": frozen_hashes,
        "hazard_drop_rate": hazard_drop, "prompt_action_agreement": agreement,
        "accepted_before_candidate_filter": sum(row["accepted"] for row in novel),
        "candidate_skips": len(candidate_skips), "surviving_rows": len(accepted),
        "surviving_by_type": dict(Counter(row["type"] for row in accepted)),
        "gates": gates, "status": "passed" if all(gates.values()) else "failed"}
    (results / "accepted.json").write_text(json.dumps(accepted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not all(gates.values()):
        (results / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return report

    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    by_record: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in accepted:
        by_record[int(row["record"])].append(row)
    change_log = []
    unchanged_identical = True
    for record in sorted(baseline):
        raw = (inputs / f"{record}.txt").read_text(encoding="utf-8")
        source = baseline[record]
        remove: set[int] = set()
        additions = []
        for row in by_record.get(record, []):
            rel, hits = relation(row, source)
            if rel == "contained_same_type":
                assertions = list(dict.fromkeys(a for index in hits for a in source[index].get("assertions", [])))
                candidates = list(dict.fromkeys(c for index in hits for c in source[index].get("candidates", [])))
                remove.update(hits)
            else:
                entity = Entity(text=row["text"], type=row["type"], position=tuple(row["position"]))
                assertions = infer_assertions(entity, raw)
                candidates = list(row.get("alias_candidates") or [])
            additions.append(Entity(text=row["text"], type=row["type"], assertions=assertions,
                                    candidates=candidates if row["type"] in {"CHẨN_ĐOÁN", "THUỐC"} else None,
                                    position=tuple(row["position"])).to_dict())
        unchanged = [row for index, row in enumerate(source) if index not in remove]
        combined = sorted([*unchanged, *additions], key=lambda row: (*row["position"], row["type"]))
        unchanged_identical &= all(row in combined for row in unchanged)
        (output / f"{record}.json").write_text(json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if remove or additions:
            change_log.append({"record": record, "removed": [source[i] for i in sorted(remove)], "added": additions})
    validation = validate_output_dir(inputs, output)
    if not validation["ok"]:
        raise ValueError(json.dumps(validation, ensure_ascii=False))
    package_output(output, zip_path, inputs)
    report.update({"unaffected_entities_identical": unchanged_identical,
                   "changed_records": len(change_log),
                   "removed_rows": sum(len(row["removed"]) for row in change_log),
                   "added_rows": sum(len(row["added"]) for row in change_log),
                   "validation": validation,
                   "zip_sha256": hashlib.sha256(Path(zip_path).read_bytes()).hexdigest(),
                   "changes": change_log})
    (results / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="turn2/input")
    parser.add_argument("--baseline", default="turn2/output_v9_verified_symptoms")
    parser.add_argument("--baseline-zip", default="turn2/output_v9_verified_symptoms.zip")
    parser.add_argument("--output", default="turn2/output_v10_multiview_consensus")
    parser.add_argument("--zip", default="turn2/output_v10_multiview_consensus.zip")
    parser.add_argument("--results", default="experiments/H38_multiview_consensus/results")
    args = parser.parse_args()
    print(json.dumps(run_experiment(args.input, args.baseline, args.output, args.zip,
                                    args.results, args.baseline_zip), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
