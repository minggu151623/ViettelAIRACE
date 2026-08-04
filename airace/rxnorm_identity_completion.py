from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from .package_output import package_output
from .rxnorm_exact_brand import load_unique_active_brands, normalize_alias
from .schema import Entity, entities_from_json
from .serialization import dumps_btc
from .validator import validate_entities, validate_output_dir


EXPECTED_H69_SHA256 = "12090622102ab333f3f697161953f1fdd1a799488ea0656a9fc0582c16462369"
EXCLUDED_CONTAINED_BRANDS = {"mucinex"}


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_active_ttys(conso_path: str | Path) -> dict[str, set[str]]:
    result: dict[str, set[str]] = defaultdict(set)
    with Path(conso_path).open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            columns = line.rstrip("\n").split("|")
            if len(columns) < 17 or columns[1] != "ENG" or columns[11] != "RXNORM":
                continue
            if columns[16] not in {"", "N"}:
                continue
            result[columns[0]].add(columns[12])
    return dict(result)


def select_contained_brand(
    entity: Entity, unique_brands: dict[str, str]
) -> tuple[str, str] | None:
    if entity.type != "THUỐC" or len(entity.candidates or []) != 1:
        return None
    mention = normalize_alias(entity.text)
    hits = {
        (alias, code)
        for alias, code in unique_brands.items()
        if len(alias) >= 4
        and alias not in EXCLUDED_CONTAINED_BRANDS
        and alias != mention
        and re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", mention)
    }
    codes = {code for _, code in hits}
    if len(codes) != 1:
        return None
    code = next(iter(codes))
    if entity.candidates == [code]:
        return None
    alias = max(alias for alias, hit_code in hits if hit_code == code)
    return code, alias


def repeated_identity_targets(
    records: list[tuple[int, list[Entity]]], active_ttys: dict[str, set[str]]
) -> dict[str, str]:
    groups: dict[str, list[Entity]] = defaultdict(list)
    for _, entities in records:
        for entity in entities:
            if entity.type == "THUỐC":
                groups[normalize_alias(entity.text)].append(entity)

    targets: dict[str, str] = {}
    for mention, entities in groups.items():
        if len(entities) < 2:
            continue
        codes = {
            entity.candidates[0]
            for entity in entities
            if len(entity.candidates or []) == 1
        }
        if len(codes) == 1 and any(not entity.candidates for entity in entities):
            targets[mention] = next(iter(codes))
            continue
        ingredient_codes = [code for code in codes if "IN" in active_ttys.get(code, set())]
        if len(ingredient_codes) == 1 and len(codes) > 1:
            targets[mention] = ingredient_codes[0]
    return targets


def build_identity_completion_submission(
    input_dir: str | Path,
    baseline_dir: str | Path,
    output_dir: str | Path,
    conso_path: str | Path,
    zip_path: str | Path,
    report_path: str | Path,
) -> dict[str, Any]:
    inputs, baseline, output = Path(input_dir), Path(baseline_dir), Path(output_dir)
    target_zip, report_target = Path(zip_path), Path(report_path)
    if sha256(baseline.with_suffix(".zip")) != EXPECTED_H69_SHA256:
        raise ValueError("H69 SHA-256 mismatch")
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError(f"output directory must be empty: {output}")

    unique_brands = load_unique_active_brands(conso_path)
    active_ttys = load_active_ttys(conso_path)
    loaded: list[tuple[int, str, list[dict[str, Any]], list[Entity]]] = []
    for text_path in sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem)):
        raw = text_path.read_text(encoding="utf-8")
        source = json.loads((baseline / f"{text_path.stem}.json").read_text(encoding="utf-8"))
        entities = entities_from_json(source)
        validate_entities(entities, raw)
        loaded.append((int(text_path.stem), raw, source, entities))

    repeat_targets = repeated_identity_targets(
        [(record, entities) for record, _, _, entities in loaded], active_ttys
    )
    changes: list[dict[str, Any]] = []
    for record, raw, source, entities in loaded:
        for index, entity in enumerate(entities):
            brand = select_contained_brand(entity, unique_brands)
            if brand is not None:
                new_code, alias = brand
                old = list(entity.candidates or [])
                entity.candidates = [new_code]
                changes.append({
                    "record": record, "entity_index": index, "text": entity.text,
                    "position": list(entity.position), "old_candidates": old,
                    "new_candidates": [new_code], "rule": "contained_unique_brand",
                    "evidence": {"alias": alias, "tty": "BN"},
                })
                continue
            mention = normalize_alias(entity.text)
            target = repeat_targets.get(mention)
            if entity.type == "THUỐC" and target and entity.candidates != [target]:
                old = list(entity.candidates or [])
                entity.candidates = [target]
                changes.append({
                    "record": record, "entity_index": index, "text": entity.text,
                    "position": list(entity.position), "old_candidates": old,
                    "new_candidates": [target], "rule": "repeated_exact_identity",
                    "evidence": {"normalized_complete_span": mention},
                })

        transformed = [entity.to_dict() for entity in entities]
        for before, after in zip(source, transformed):
            for key in set(before) | set(after):
                if key != "candidates" and before.get(key) != after.get(key):
                    raise AssertionError(f"frozen field changed: {key}")
            if before.get("type") != "THUỐC" and before.get("candidates") != after.get("candidates"):
                raise AssertionError("non-drug candidate changed")
        validate_entities(entities, raw)
        (output / f"{record}.json").write_text(dumps_btc(transformed), encoding="utf-8")

    brand_rows = sum(row["rule"] == "contained_unique_brand" for row in changes)
    repeat_rows = sum(row["rule"] == "repeated_exact_identity" for row in changes)
    validation = validate_output_dir(inputs, output)
    gates = {
        "changed_rows_between_10_and_20": 10 <= len(changes) <= 20,
        "changed_records_ge_8": len({row["record"] for row in changes}) >= 8,
        "contained_brand_rows_exactly_9": brand_rows == 9,
        "repeated_identity_rows_exactly_4": repeat_rows == 4,
        "all_contained_codes_active_bn": all(
            "BN" in active_ttys.get(row["new_candidates"][0], set())
            for row in changes if row["rule"] == "contained_unique_brand"
        ),
        "all_100_records_validate": validation["ok"] and validation["records"] == 100,
    }
    if not all(gates.values()):
        raise RuntimeError(f"H71 gates failed: {gates}")

    package_output(output, target_zip, inputs)
    repeat_zip = report_target.parent / "repeat.zip"
    package_output(output, repeat_zip, inputs)
    deterministic = target_zip.read_bytes() == repeat_zip.read_bytes()
    repeat_zip.unlink()
    if not deterministic:
        raise RuntimeError("ZIP packaging is not deterministic")

    report = {
        "hypothesis": "H71_rxnorm_identity_completion",
        "status": "PASS_AWAITING_SUBMISSION_APPROVAL",
        "baseline_zip_sha256": EXPECTED_H69_SHA256,
        "zip": str(target_zip), "zip_sha256": sha256(target_zip),
        "zip_bytes": target_zip.stat().st_size,
        "changed_rows": len(changes),
        "changed_records": len({row["record"] for row in changes}),
        "contained_brand_rows": brand_rows, "repeated_identity_rows": repeat_rows,
        "gates": {**gates, "deterministic_zip_bytes": deterministic},
        "validation": validation, "changes": changes,
    }
    report_target.parent.mkdir(parents=True, exist_ok=True)
    report_target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
