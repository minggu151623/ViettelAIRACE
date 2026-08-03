"""H59 target merger: H38 plus exact PhoNER-supported Qwen clinical spans."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from transformers import AutoModelForTokenClassification

from .assertions import infer_assertions
from .multiview_consensus import overlap
from .package_output import package_output
from .phoner_boundary import _boundary_set
from .schema import CANDIDATE_TYPES, Entity
from .section_expert_core import BASELINE_SHA256, _load_records
from .train import _device, _load_fast_tokenizer, predict_token_entities
from .validator import validate_output_dir


ALLOWED_TYPES = {"CHẨN_ĐOÁN", "TRIỆU_CHỨNG"}


def eligible_qwen_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row for row in report["selected_rows"]
        if row["mode"] == "qwen_only_clinical_or_numeric"
        and row["type"] in ALLOWED_TYPES
    ]


def select_exact_supported(
    proposals: list[dict[str, Any]],
    support: dict[int, set[tuple[int, int]]],
) -> list[dict[str, Any]]:
    rows = [
        row for row in proposals
        if tuple(row["position"]) in support.get(int(row["record"]), set())
    ]
    return sorted(rows, key=lambda row: (row["record"], *row["position"], row["type"]))


def target_support(
    checkpoint: str | Path,
    input_dir: str | Path,
    threshold: float,
) -> tuple[dict[int, set[tuple[int, int]]], dict[int, list[dict[str, Any]]]]:
    tokenizer = _load_fast_tokenizer(checkpoint)
    model = AutoModelForTokenClassification.from_pretrained(str(checkpoint))
    device = _device()
    model.to(device)
    support: dict[int, set[tuple[int, int]]] = {}
    audit: dict[int, list[dict[str, Any]]] = {}
    for record in range(1, 101):
        raw = (Path(input_dir) / f"{record}.txt").read_text(encoding="utf-8")
        entities = predict_token_entities(
            raw, model=model, tokenizer=tokenizer, device=device,
            max_length=256, stride=64,
        )
        support[record] = _boundary_set(entities, threshold)
        audit[record] = [
            {
                "text": entity.text,
                "position": list(entity.position),
                "confidence": round(float(entity.confidence), 6),
            }
            for entity in entities if float(entity.confidence) >= threshold
        ]
    return support, audit


def build(
    input_dir: Path,
    baseline_dir: Path,
    baseline_zip: Path,
    h58_report: Path,
    checkpoint: Path,
    threshold: float,
    output_dir: Path,
    zip_path: Path,
) -> dict[str, Any]:
    observed = hashlib.sha256(baseline_zip.read_bytes()).hexdigest()
    if observed != BASELINE_SHA256:
        raise ValueError(f"H59 baseline hash mismatch: {observed}")
    baseline = _load_records(baseline_dir)
    h58 = json.loads(h58_report.read_text(encoding="utf-8"))
    proposals = eligible_qwen_rows(h58)
    support, audit = target_support(checkpoint, input_dir, threshold)
    selected = select_exact_supported(proposals, support)

    # Recheck the frozen disjoint requirement instead of trusting upstream
    # metadata. Any overlap makes the row ineligible rather than replacing H38.
    disjoint: list[dict[str, Any]] = []
    rejected_overlap = 0
    for row in selected:
        if any(overlap(tuple(row["position"]), tuple(old["position"]))
               for old in baseline[int(row["record"])]):
            rejected_overlap += 1
        else:
            disjoint.append(row)
    selected = disjoint
    by_record: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in selected:
        by_record[int(row["record"])].append(row)

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    for record in range(1, 101):
        raw = (input_dir / f"{record}.txt").read_text(encoding="utf-8")
        rows = [dict(row) for row in baseline[record]]
        for proposal in by_record[record]:
            entity = Entity(
                text=proposal["text"],
                type=proposal["type"],
                position=tuple(proposal["position"]),
                assertions=list(infer_assertions(
                    Entity(
                        text=proposal["text"], type=proposal["type"],
                        position=tuple(proposal["position"]),
                    ),
                    raw,
                )),
                candidates=[] if proposal["type"] in CANDIDATE_TYPES else None,
                source="h59_phoner_exact_qwen",
            )
            rows.append(entity.to_dict())
        rows.sort(key=lambda row: (*row["position"], row["type"], row["text"]))
        (output_dir / f"{record}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    validation = validate_output_dir(input_dir, output_dir, position_mode="raw")
    gates = {
        "baseline_hash_matches": True,
        "every_added_row_has_exact_H59_boundary_support": all(
            tuple(row["position"]) in support[row["record"]] for row in selected
        ),
        "at_least_20_and_at_most_100_added_rows": 20 <= len(selected) <= 100,
        "no_baseline_rows_changed_or_removed": all(
            all(row in json.loads((output_dir / f"{record}.json").read_text(encoding="utf-8"))
                for row in baseline[record])
            for record in range(1, 101)
        ),
        "no_new_nonempty_candidate_codes": all(not row.get("candidates") for row in selected),
        "all_100_records_validate": validation["ok"],
    }
    report: dict[str, Any] = {
        "hypothesis": "H59_phoner_boundary_teacher",
        "threshold": threshold,
        "eligible_qwen_clinical": len(proposals),
        "added_rows": len(selected),
        "added_types": dict(Counter(row["type"] for row in selected)),
        "records_changed": len({row["record"] for row in selected}),
        "rejected_baseline_overlap": rejected_overlap,
        "selected_rows": selected,
        "target_teacher_audit": audit,
        "validation": validation,
        "gates": gates,
        "decision": "PASS" if all(gates.values()) else "FAIL",
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
    parser.add_argument("--h58-report", type=Path, default=Path("experiments/H58_section_expert_recall/results/report.json"))
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--threshold", type=float, required=True)
    parser.add_argument("--output", type=Path, default=Path("turn2/output_v15_phoner_boundary_teacher"))
    parser.add_argument("--zip", type=Path, default=Path("turn2/output_v15_phoner_boundary_teacher.zip"))
    parser.add_argument("--report", type=Path, default=Path("experiments/H59_phoner_boundary_teacher/results/target_report.json"))
    args = parser.parse_args()
    report = build(
        args.input, args.baseline, args.baseline_zip, args.h58_report,
        args.checkpoint, args.threshold, args.output, args.zip,
    )
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in report.items()
                      if key not in {"selected_rows", "target_teacher_audit"}},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
