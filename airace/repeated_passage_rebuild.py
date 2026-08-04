from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .package_output import package_output
from .repeated_passage_consistency import (
    Occurrence,
    RelativeEntity,
    _view_rows,
    canonical,
    repeated_lines,
    signature,
)
from .serialization import dumps_btc
from .validator import validate_output_dir


EXPECTED_H69_SHA256 = "12090622102ab333f3f697161953f1fdd1a799488ea0656a9fc0582c16462369"
CANDIDATE_TYPES = {"CHẨN_ĐOÁN", "THUỐC"}


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(row: dict[str, Any], occurrence: Occurrence) -> bool:
    start, end = row["position"]
    return occurrence.start <= start and end <= occurrence.end


def _crosses(row: dict[str, Any], occurrence: Occurrence) -> bool:
    start, end = row["position"]
    return start < occurrence.start < end or start < occurrence.end < end


def _overlap(row: dict[str, Any], start: int, end: int) -> int:
    return max(0, min(row["position"][1], end) - max(row["position"][0], start))


def rebuild_occurrence(
    raw: str,
    occurrence: Occurrence,
    selected: list[RelativeEntity],
    source_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Create one canonical signature using only metadata from this occurrence."""

    local = [(index, row) for index, row in enumerate(source_rows) if _inside(row, occurrence)]
    available = {index for index, _ in local}
    assignments: dict[RelativeEntity, int] = {}

    # Preserve exact local entities first.
    for entity in selected:
        absolute = (occurrence.start + entity.start, occurrence.start + entity.end)
        exact = [
            index for index, row in local
            if index in available and tuple(row["position"]) == absolute and row["type"] == entity.type
        ]
        if exact:
            assignments[entity] = exact[0]
            available.remove(exact[0])

    # Rebounded entities may inherit metadata from one maximum-overlap local row.
    pairs: list[tuple[int, int, int, RelativeEntity, int]] = []
    for entity in selected:
        if entity in assignments:
            continue
        start, end = occurrence.start + entity.start, occurrence.start + entity.end
        for index, row in local:
            if index not in available or row["type"] != entity.type:
                continue
            overlap = _overlap(row, start, end)
            if overlap:
                pairs.append((overlap, -(end - start), -index, entity, index))
    for _, _, _, entity, index in sorted(pairs, reverse=True):
        if entity in assignments or index not in available:
            continue
        assignments[entity] = index
        available.remove(index)

    rebuilt: list[dict[str, Any]] = []
    for entity in sorted(selected):
        start, end = occurrence.start + entity.start, occurrence.start + entity.end
        old = source_rows[assignments[entity]] if entity in assignments else None
        row: dict[str, Any] = {
            "text": raw[start:end],
            "type": entity.type,
            "assertions": list(old.get("assertions", [])) if old else [],
            "position": [start, end],
        }
        if entity.type in CANDIDATE_TYPES:
            row["candidates"] = list(old.get("candidates", [])) if old else []
        rebuilt.append(row)
    return rebuilt


def build_repeated_passage_submission(
    input_dir: str | Path,
    baseline_dir: str | Path,
    output_dir: str | Path,
    baseline_zip: str | Path,
    h69_report_path: str | Path,
    zip_path: str | Path,
    report_path: str | Path,
) -> dict[str, Any]:
    inputs, baseline, output = Path(input_dir), Path(baseline_dir), Path(output_dir)
    target_zip, report_target = Path(zip_path), Path(report_path)
    if sha256(baseline_zip) != EXPECTED_H69_SHA256:
        raise ValueError("H69 SHA-256 mismatch")
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError(f"output directory must be empty: {output}")

    sources = {
        int(path.stem): json.loads(path.read_text(encoding="utf-8"))
        for path in baseline.glob("*.json")
    }
    raw_texts = {
        int(path.stem): path.read_text(encoding="utf-8")
        for path in inputs.glob("*.txt")
    }
    brand_rows = json.loads(Path(h69_report_path).read_text(encoding="utf-8"))["changes"]
    frozen_brands = {
        (row["record"], tuple(row["position"])): row for row in brand_rows
    }

    groups = repeated_lines(inputs)
    views = _view_rows()
    selected_regions: dict[int, list[tuple[str, Occurrence, list[RelativeEntity]]]] = {}
    affected_groups: list[dict[str, Any]] = []
    symmetric_difference = 0

    for text, occurrences in groups.items():
        selected, ties = canonical(text, occurrences, views)
        differences = sum(
            len(signature(sources[occurrence.record], occurrence).symmetric_difference(set(selected)))
            for occurrence in occurrences
        )
        if not differences:
            continue
        touches_brand = any(
            (occurrence.record, tuple(row["position"])) in frozen_brands
            for occurrence in occurrences
            for row in sources[occurrence.record]
            if _inside(row, occurrence)
        )
        crossing = any(
            _crosses(row, occurrence)
            for occurrence in occurrences
            for row in sources[occurrence.record]
        )
        if touches_brand or crossing:
            continue
        symmetric_difference += differences
        affected_groups.append({
            "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            "occurrences": len(occurrences),
            "records": sorted({item.record for item in occurrences}),
            "canonical_entities": len(selected),
            "span_type_symmetric_difference": differences,
            "excluded_cross_type_ties": ties,
        })
        for occurrence in occurrences:
            selected_regions.setdefault(occurrence.record, []).append((text, occurrence, selected))

    changed_records: set[int] = set()
    for record in range(1, 101):
        source_rows = sources[record]
        regions = sorted(selected_regions.get(record, []), key=lambda item: item[1].start)
        removed_indices = {
            index
            for _, occurrence, _ in regions
            for index, row in enumerate(source_rows)
            if _inside(row, occurrence)
        }
        output_rows = [dict(row) for index, row in enumerate(source_rows) if index not in removed_indices]
        for _, occurrence, selected in regions:
            rebuilt = rebuild_occurrence(raw_texts[record], occurrence, selected, source_rows)
            if signature(source_rows, occurrence) != signature(rebuilt, occurrence):
                changed_records.add(record)
            output_rows.extend(rebuilt)
        output_rows.sort(key=lambda row: (row["position"][0], row["position"][1], row["type"], row["text"]))
        (output / f"{record}.json").write_text(dumps_btc(output_rows), encoding="utf-8")

    validation = validate_output_dir(inputs, output)
    frozen_brand_ok = True
    for (record, position), expected in frozen_brands.items():
        rows = json.loads((output / f"{record}.json").read_text(encoding="utf-8"))
        matches = [row for row in rows if tuple(row["position"]) == position and row["type"] == "THUỐC"]
        frozen_brand_ok &= len(matches) == 1 and matches[0].get("candidates") == expected["new_candidates"]

    gates = {
        "affected_groups_between_100_and_130": 100 <= len(affected_groups) <= 130,
        "symmetric_difference_between_450_and_650": 450 <= symmetric_difference <= 650,
        "changed_records_ge_70": len(changed_records) >= 70,
        "all_H69_brand_rows_preserved": frozen_brand_ok,
        "all_100_records_validate": validation["ok"] and validation["records"] == 100,
    }
    if not all(gates.values()):
        raise RuntimeError(f"H72 gates failed: {gates}")

    package_output(output, target_zip, inputs)
    repeat_zip = report_target.parent / "repeat.zip"
    package_output(output, repeat_zip, inputs)
    deterministic = target_zip.read_bytes() == repeat_zip.read_bytes()
    repeat_zip.unlink()
    if not deterministic:
        raise RuntimeError("ZIP packaging is not deterministic")

    report = {
        "hypothesis": "H72_repeated_passage_multiview_rebuild",
        "status": "PASS_HIGH_RISK_AWAITING_SUBMISSION_APPROVAL",
        "risk_class": "high_upside_final_day_challenger",
        "baseline_zip_sha256": EXPECTED_H69_SHA256,
        "zip": str(target_zip), "zip_sha256": sha256(target_zip),
        "zip_bytes": target_zip.stat().st_size,
        "affected_groups": len(affected_groups),
        "affected_occurrences": sum(row["occurrences"] for row in affected_groups),
        "changed_records": len(changed_records),
        "span_type_symmetric_difference": symmetric_difference,
        "gates": {**gates, "deterministic_zip_bytes": deterministic},
        "validation": validation,
        "groups": affected_groups,
    }
    report_target.parent.mkdir(parents=True, exist_ok=True)
    report_target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
