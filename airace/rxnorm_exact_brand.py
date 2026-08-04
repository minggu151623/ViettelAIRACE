from __future__ import annotations

import hashlib
import json
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from .package_output import package_output
from .schema import Entity, entities_from_json
from .serialization import dumps_btc
from .validator import validate_entities, validate_output_dir


ALLOWED_SOURCES = {"RXNORM", "MTHSPL"}
EXPECTED_H38_SHA256 = "a9b9ae07997e57080ed8ce2ad9c390f4cd8c229e8eae8de447f6f47ae6ff4d0b"


def normalize_alias(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_unique_active_brands(conso_path: str | Path) -> dict[str, str]:
    """Return exact normalized BN aliases that identify one active RxCUI."""

    aliases: dict[str, set[str]] = defaultdict(set)
    with Path(conso_path).open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            columns = line.rstrip("\n").split("|")
            if len(columns) < 17:
                continue
            if columns[1] != "ENG" or columns[11] not in ALLOWED_SOURCES:
                continue
            if columns[12] != "BN" or columns[16] not in {"", "N"}:
                continue
            rxcui, term = columns[0], columns[14].strip()
            if rxcui and term:
                aliases[normalize_alias(term)].add(rxcui)
    return {
        alias: next(iter(codes))
        for alias, codes in aliases.items()
        if alias and len(codes) == 1
    }


def select_exact_brand_replacement(
    entity: Entity, unique_brands: dict[str, str]
) -> str | None:
    if entity.type != "THUỐC" or len(entity.candidates or []) != 1:
        return None
    new_code = unique_brands.get(normalize_alias(entity.text))
    if not new_code or new_code == entity.candidates[0]:
        return None
    return new_code


def _frozen_projection(value: dict[str, Any]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key != "candidates"}


def build_exact_brand_submission(
    input_dir: str | Path,
    baseline_dir: str | Path,
    output_dir: str | Path,
    conso_path: str | Path,
    zip_path: str | Path,
    report_path: str | Path,
) -> dict[str, Any]:
    inputs = Path(input_dir)
    baseline = Path(baseline_dir)
    output = Path(output_dir)
    target_zip = Path(zip_path)
    report_target = Path(report_path)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError(f"output directory must be empty: {output}")

    baseline_zip = baseline.with_suffix(".zip")
    baseline_sha256 = sha256(baseline_zip)
    if baseline_sha256 != EXPECTED_H38_SHA256:
        raise ValueError(
            f"H38 SHA-256 mismatch: {baseline_sha256} != {EXPECTED_H38_SHA256}"
        )

    unique_brands = load_unique_active_brands(conso_path)
    changes: list[dict[str, Any]] = []
    changed_mentions: dict[str, set[str]] = defaultdict(set)
    total_entities = 0

    records = sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem))
    if [path.stem for path in records] != [str(index) for index in range(1, 101)]:
        raise ValueError("expected input/1.txt through input/100.txt")

    for text_path in records:
        raw_text = text_path.read_text(encoding="utf-8")
        baseline_path = baseline / f"{text_path.stem}.json"
        source_values = json.loads(baseline_path.read_text(encoding="utf-8"))
        entities = entities_from_json(source_values)
        validate_entities(entities, raw_text)

        for index, entity in enumerate(entities):
            new_code = select_exact_brand_replacement(entity, unique_brands)
            if new_code is None:
                continue
            old_candidates = list(entity.candidates or [])
            entity.candidates = [new_code]
            normalized = normalize_alias(entity.text)
            changed_mentions[normalized].add(new_code)
            changes.append(
                {
                    "record": int(text_path.stem),
                    "entity_index": index,
                    "text": entity.text,
                    "position": list(entity.position),
                    "old_candidates": old_candidates,
                    "new_candidates": [new_code],
                    "evidence": "unique active full-span RxNorm BN alias",
                }
            )

        output_values = [entity.to_dict() for entity in entities]
        if len(output_values) != len(source_values):
            raise AssertionError("entity count changed")
        for source, transformed in zip(source_values, output_values):
            if _frozen_projection(source) != _frozen_projection(transformed):
                raise AssertionError("a frozen field changed")
            if source.get("type") != "THUỐC" and source.get("candidates") != transformed.get("candidates"):
                raise AssertionError("a non-drug candidate changed")
        validate_entities(entities, raw_text)
        (output / baseline_path.name).write_text(
            dumps_btc(output_values), encoding="utf-8"
        )
        total_entities += len(entities)

    validation = validate_output_dir(inputs, output, position_mode="raw")
    repeated_consistent = all(len(codes) == 1 for codes in changed_mentions.values())
    changed_records = len({row["record"] for row in changes})
    gates = {
        "changed_rows_ge_20": len(changes) >= 20,
        "changed_rows_le_60": len(changes) <= 60,
        "changed_records_ge_10": changed_records >= 10,
        "all_new_codes_active_tty_bn": all(
            unique_brands.get(normalize_alias(row["text"])) == row["new_candidates"][0]
            for row in changes
        ),
        "repeated_mentions_consistent": repeated_consistent,
        "all_100_records_validate": validation["ok"] and validation["records"] == 100,
    }
    if not all(gates.values()):
        raise RuntimeError(f"H69 build gates failed: {gates}")

    package_output(output, target_zip, inputs, position_mode="raw")
    repeat_zip = report_target.parent / "repeat.zip"
    package_output(output, repeat_zip, inputs, position_mode="raw")
    deterministic = target_zip.read_bytes() == repeat_zip.read_bytes()
    if not deterministic:
        raise RuntimeError("ZIP packaging is not deterministic")
    repeat_zip.unlink()

    report = {
        "hypothesis": "H69_rxnorm_exact_brand_identity",
        "status": "PASS_AWAITING_SUBMISSION_APPROVAL",
        "baseline": str(baseline),
        "baseline_zip_sha256": baseline_sha256,
        "output": str(output),
        "zip": str(target_zip),
        "zip_sha256": sha256(target_zip),
        "zip_bytes": target_zip.stat().st_size,
        "records": len(records),
        "entities": total_entities,
        "unique_active_brand_aliases": len(unique_brands),
        "changed_rows": len(changes),
        "changed_records": changed_records,
        "unique_changed_mentions": len(changed_mentions),
        "gates": {**gates, "deterministic_zip_bytes": deterministic},
        "validation": validation,
        "changes": changes,
    }
    report_target.parent.mkdir(parents=True, exist_ok=True)
    report_target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report
