"""H60: resegment unambiguous H38 clinical rows with the frozen H59 teacher."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .multiview_consensus import overlap
from .package_output import package_output
from .section_expert_core import BASELINE_SHA256, _load_records
from .validator import validate_output_dir


MODEL_SHA256 = "a3d005f86d6ff4a377463b338cc49a79968dc183ccd639a4477ff901dd62b430"
CLINICAL_TYPES = {"CHẨN_ĐOÁN", "TRIỆU_CHỨNG"}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_replacements(
    baseline: dict[int, list[dict[str, Any]]],
    teacher_audit: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], Counter[str]]:
    candidates: list[dict[str, Any]] = []
    rejected: Counter[str] = Counter()
    for record_text, teacher_rows in teacher_audit.items():
        record = int(record_text)
        for teacher in teacher_rows:
            teacher_position = tuple(teacher["position"])
            hits = [
                index for index, row in enumerate(baseline[record])
                if overlap(teacher_position, tuple(row["position"]))
            ]
            if len(hits) != 1:
                rejected["not_exactly_one_baseline_overlap"] += 1
                continue
            baseline_index = hits[0]
            old = baseline[record][baseline_index]
            old_position = tuple(old["position"])
            if teacher_position == old_position:
                rejected["exact_confirmation"] += 1
                continue
            if old["type"] not in CLINICAL_TYPES:
                rejected["nonclinical_baseline_type"] += 1
                continue
            if (teacher_position[0] >= old_position[0]
                    and teacher_position[1] <= old_position[1]):
                relation = "teacher_strictly_inside_baseline"
            elif (old_position[0] >= teacher_position[0]
                  and old_position[1] <= teacher_position[1]):
                relation = "baseline_strictly_inside_teacher"
            else:
                rejected["partial_overlap"] += 1
                continue
            candidates.append(
                {
                    "record": record,
                    "baseline_index": baseline_index,
                    "old_text": old["text"],
                    "old_position": list(old_position),
                    "new_text": teacher["text"],
                    "new_position": list(teacher_position),
                    "confidence": teacher["confidence"],
                    "relation": relation,
                    "type": old["type"],
                }
            )

    by_target: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        by_target[(row["record"], row["baseline_index"])].append(row)
    selected: list[dict[str, Any]] = []
    for rows in by_target.values():
        if len(rows) != 1:
            rejected["competing_teacher_spans"] += len(rows)
            continue
        selected.append(rows[0])
    selected.sort(key=lambda row: (row["record"], row["baseline_index"]))
    return selected, rejected


def _has_overlap(rows: list[dict[str, Any]]) -> bool:
    ordered = sorted(rows, key=lambda row: (*row["position"], row["type"]))
    return any(
        overlap(tuple(left["position"]), tuple(right["position"]))
        for index, left in enumerate(ordered)
        for right in ordered[index + 1:]
    )


def build(
    input_dir: Path,
    baseline_dir: Path,
    baseline_zip: Path,
    checkpoint_model: Path,
    source_report: Path,
    target_report: Path,
    output_dir: Path,
    zip_path: Path,
) -> dict[str, Any]:
    baseline_hash = _sha256(baseline_zip)
    if baseline_hash != BASELINE_SHA256:
        raise ValueError(f"H60 baseline hash mismatch: {baseline_hash}")
    model_hash = _sha256(checkpoint_model)
    if model_hash != MODEL_SHA256:
        raise ValueError(f"H60 teacher hash mismatch: {model_hash}")
    calibration = json.loads(source_report.read_text(encoding="utf-8"))
    target = json.loads(target_report.read_text(encoding="utf-8"))
    baseline = _load_records(baseline_dir)
    selected, rejected = select_replacements(baseline, target["target_teacher_audit"])
    by_record = defaultdict(list)
    for row in selected:
        by_record[row["record"]].append(row)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    inherited_fields_ok = True
    counts_unchanged = True
    final_overlap = False
    for record in range(1, 101):
        raw = (input_dir / f"{record}.txt").read_text(encoding="utf-8")
        rows = [dict(row) for row in baseline[record]]
        for change in by_record[record]:
            index = change["baseline_index"]
            old = rows[index]
            new = dict(old)
            start, end = change["new_position"]
            new["text"] = raw[start:end]
            new["position"] = [start, end]
            inherited_fields_ok &= all(
                new.get(field) == old.get(field)
                for field in ("type", "assertions", "candidates")
            )
            rows[index] = new
        rows.sort(key=lambda row: (*row["position"], row["type"], row["text"]))
        counts_unchanged &= len(rows) == len(baseline[record])
        final_overlap |= _has_overlap(rows)
        (output_dir / f"{record}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    validation = validate_output_dir(input_dir, output_dir, position_mode="raw")
    gates = {
        "baseline_hash_matches": True,
        "teacher_model_hash_matches": True,
        "source_calibration_decision_is_PASS": calibration.get("decision") == "PASS",
        "at_least_120_and_at_most_180_replacements": 120 <= len(selected) <= 180,
        "every_replacement_is_one_to_one_strict_containment": all(
            row["relation"] in {
                "teacher_strictly_inside_baseline",
                "baseline_strictly_inside_teacher",
            }
            for row in selected
        ),
        "no_baseline_additions_or_net_deletions": counts_unchanged,
        "type_assertions_candidates_unchanged_per_replaced_row": inherited_fields_ok,
        "no_overlapping_final_entities": not final_overlap,
        "all_100_records_validate": validation["ok"],
    }
    report: dict[str, Any] = {
        "hypothesis": "H60_phoner_boundary_resegmentation",
        "teacher_model_sha256": model_hash,
        "teacher_threshold": target["threshold"],
        "replacements": len(selected),
        "records_changed": len({row["record"] for row in selected}),
        "relations": dict(Counter(row["relation"] for row in selected)),
        "types": dict(Counter(row["type"] for row in selected)),
        "rejected": dict(rejected),
        "selected_rows": selected,
        "validation": validation,
        "gates": gates,
        "decision": "PASS" if all(gates.values()) else "FAIL",
    }
    if report["decision"] == "PASS":
        package_output(output_dir, zip_path)
        first = _sha256(zip_path)
        repeat = zip_path.with_name(zip_path.stem + "_repeat.zip")
        package_output(output_dir, repeat)
        second = _sha256(repeat)
        repeat.unlink()
        report.update(
            zip_sha256=first,
            repeat_zip_sha256=second,
            byte_identical_repeat=first == second,
        )
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
    parser.add_argument("--checkpoint-model", type=Path, default=Path("models/h59-phoner-boundary/model.safetensors"))
    parser.add_argument("--source-report", type=Path, default=Path("experiments/H59_phoner_boundary_teacher/results/source_calibration.json"))
    parser.add_argument("--target-report", type=Path, default=Path("experiments/H59_phoner_boundary_teacher/results/target_report.json"))
    parser.add_argument("--output", type=Path, default=Path("turn2/output_v16_phoner_boundary_resegmentation"))
    parser.add_argument("--zip", type=Path, default=Path("turn2/output_v16_phoner_boundary_resegmentation.zip"))
    parser.add_argument("--report", type=Path, default=Path("experiments/H60_phoner_boundary_resegmentation/results/report.json"))
    args = parser.parse_args()
    report = build(
        args.input, args.baseline, args.baseline_zip, args.checkpoint_model,
        args.source_report, args.target_report, args.output, args.zip,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in report.items()
                      if key != "selected_rows"}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
