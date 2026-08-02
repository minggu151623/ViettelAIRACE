"""Integrate only H36-verified symptom boundaries into the frozen H23 output."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

from .assertions import infer_assertions
from .package_output import package_output
from .schema import Entity
from .validator import validate_output_dir


EXPECTED_BASELINE_SHA256 = "e1fc83b8e53cd9d4ac3f5d7f072a4f34eb46ee7841243a52f690ae8645514662"
EXPECTED_QUEUE_SHA256 = "09ad01b03d1267014ca8bbd1f983ca471778114be766506454eb5cee090963cc"


def _sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _key(row: dict[str, Any], record: int) -> tuple[int, int, str, int]:
    return (int(row["position"][0]), int(row["position"][1]), str(row["type"]), record)


def _overlap(left: list[int], right: list[int]) -> bool:
    return max(left[0], right[0]) < min(left[1], right[1])


def _contained(inner: list[int], outer: list[int]) -> bool:
    return outer[0] <= inner[0] and inner[1] <= outer[1]


def build_verified_symptoms(
    input_dir: str | Path,
    baseline_dir: str | Path,
    baseline_zip: str | Path,
    accepted_queue: str | Path,
    agreement_report: str | Path,
    output_dir: str | Path,
    zip_path: str | Path,
    *,
    enforce_hashes: bool = True,
) -> dict[str, Any]:
    if enforce_hashes:
        if _sha256(baseline_zip) != EXPECTED_BASELINE_SHA256:
            raise ValueError("frozen H23 ZIP hash mismatch")
        if _sha256(accepted_queue) != EXPECTED_QUEUE_SHA256:
            raise ValueError("frozen H36 queue hash mismatch")

    inputs = Path(input_dir)
    baseline = Path(baseline_dir)
    output = Path(output_dir)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    accepted = json.loads(Path(accepted_queue).read_text(encoding="utf-8"))
    support_rows = json.loads(Path(agreement_report).read_text(encoding="utf-8"))["queue"]
    support = {_key(row, int(row["record"])) for row in support_rows}
    symptoms = [row for row in accepted if row["type"] == "TRIỆU_CHỨNG"]
    by_record: dict[int, list[dict[str, Any]]] = {}
    for row in symptoms:
        record = int(row["record"])
        if _key(row, record) not in support:
            raise ValueError(f"accepted row lacks independent support: {_key(row, record)}")
        by_record.setdefault(record, []).append(row)

    counts: Counter[str] = Counter()
    skipped: list[dict[str, Any]] = []
    applied_keys: list[tuple[int, int, str, int]] = []
    changes: list[dict[str, Any]] = []
    unchanged_identical = True
    records = sorted((int(path.stem) for path in inputs.glob("*.txt")))
    for record in records:
        raw = (inputs / f"{record}.txt").read_text(encoding="utf-8")
        source = json.loads((baseline / f"{record}.json").read_text(encoding="utf-8"))
        remove: set[int] = set()
        additions: list[dict[str, Any]] = []
        for row in sorted(by_record.get(record, []), key=lambda value: tuple(value["position"])):
            position = [int(row["position"][0]), int(row["position"][1])]
            overlaps = [index for index, base in enumerate(source)
                        if _overlap(position, base["position"])]
            if not overlaps:
                entity = Entity(text=row["text"], type="TRIỆU_CHỨNG",
                                position=tuple(position))
                entity.assertions = infer_assertions(entity, raw)
                additions.append(entity.to_dict())
                applied_keys.append(_key(row, record))
                counts["disjoint_additions"] += 1
                continue
            overlap_rows = [source[index] for index in overlaps]
            safe = all(base["type"] == "TRIỆU_CHỨNG" and
                       _contained(position, base["position"])
                       for base in overlap_rows)
            if not safe:
                counts["skipped_conflicts"] += 1
                skipped.append({"record": record, "text": row["text"],
                                "position": position,
                                "overlaps": overlap_rows})
                continue
            assertions: list[str] = []
            for base in overlap_rows:
                assertions.extend(base.get("assertions") or [])
            additions.append(Entity(
                text=row["text"], type="TRIỆU_CHỨNG",
                assertions=list(dict.fromkeys(assertions)),
                position=tuple(position),
            ).to_dict())
            remove.update(overlaps)
            applied_keys.append(_key(row, record))
            counts["boundary_rows"] += 1

        unchanged = [row for index, row in enumerate(source) if index not in remove]
        if remove or additions:
            changes.append({
                "record": record,
                "removed": [source[index] for index in sorted(remove)],
                "added": additions,
            })
        result = sorted([*unchanged, *additions],
                        key=lambda row: (row["position"][0], row["position"][1], row["type"]))
        unchanged_identical &= all(row in result for row in unchanged)
        (output / f"{record}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        counts["removed_baseline_rows"] += len(remove)
        counts["added_output_rows"] += len(additions)

    validation = validate_output_dir(inputs, output)
    if not validation["ok"]:
        raise ValueError(json.dumps(validation, ensure_ascii=False))
    if any("candidates" in row for record in records
           for row in json.loads((output / f"{record}.json").read_text(encoding="utf-8"))
           if row["type"] == "TRIỆU_CHỨNG"):
        raise ValueError("symptom unexpectedly contains candidates")
    package = package_output(output, zip_path, inputs)
    report = {
        "accepted_symptoms": len(symptoms),
        "applied_rows": len(applied_keys),
        "applied_unique": len(set(applied_keys)) == len(applied_keys),
        "counts": dict(counts),
        "skipped": skipped,
        "changes": changes,
        "unaffected_entities_identical": unchanged_identical,
        "validation": validation,
        "zip": package,
        "zip_sha256": _sha256(zip_path),
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="turn2/input")
    parser.add_argument("--baseline", default="turn2/output_v8_candidate_semantic")
    parser.add_argument("--baseline-zip", default="turn2/output_v8_candidate_semantic.zip")
    parser.add_argument("--queue", default="experiments/H36_controlled_novel_verifier/results/accepted_novel.json")
    parser.add_argument("--agreement", default="experiments/H35_independent_agreement_audit/results/report.json")
    parser.add_argument("--output", default="turn2/output_v9_verified_symptoms")
    parser.add_argument("--zip", default="turn2/output_v9_verified_symptoms.zip")
    args = parser.parse_args()
    report = build_verified_symptoms(args.input, args.baseline, args.baseline_zip,
                                     args.queue, args.agreement, args.output, args.zip)
    target = Path("experiments/H37_verified_symptom_boundary/results")
    target.mkdir(parents=True, exist_ok=True)
    (target / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
