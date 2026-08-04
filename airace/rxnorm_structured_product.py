from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from .package_output import package_output
from .schema import Entity, entities_from_json
from .serialization import dumps_btc
from .validator import validate_entities, validate_output_dir


EXPECTED_H69_SHA256 = "12090622102ab333f3f697161953f1fdd1a799488ea0656a9fc0582c16462369"
CURRENT_TTYS = {"IN", "PIN", "MIN", "BN"}
PRODUCT_TTYS = {"SCD", "SBD"}


def norm(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    value = re.sub(r"(?<=\d),(?=\d)", ".", value)
    return " ".join(value.split())


def sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_strength_and_form(text: str) -> dict[str, Any] | None:
    value = norm(text)
    strength_match = re.search(r"(\d+(?:\.\d+)?)\s*(mcg|mg|g|unit|đơn vị)\b", value)
    if not strength_match:
        return None
    amount = float(strength_match.group(1))
    unit = strength_match.group(2)
    if unit == "g":
        amount *= 1000
        unit = "mg"
    elif unit == "đơn vị":
        unit = "unit"
    routes: set[str] = set()
    forms: set[str] = set()
    if re.search(r"\biv\b|tĩnh mạch|tiêm", value):
        routes.add("injection")
    if re.search(r"\bpo\b|uống", value):
        routes.add("oral")
    if re.search(r"\bviên\b|tablet", value):
        forms.add("tablet")
    if re.search(r"capsule|viên nang", value):
        forms.add("capsule")
    if "injection" in routes:
        forms.add("injection")
    if not routes and not forms:
        return None
    return {"amount": amount, "unit": unit, "routes": routes, "forms": forms}


def load_concepts(conso_path: str | Path) -> dict[str, dict[str, Any]]:
    concepts: dict[str, dict[str, Any]] = defaultdict(lambda: {"ttys": set(), "names": []})
    with Path(conso_path).open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            columns = line.rstrip("\n").split("|")
            if len(columns) < 17 or columns[1] != "ENG" or columns[11] != "RXNORM":
                continue
            if columns[16] not in {"", "N"}:
                continue
            code, tty, name = columns[0], columns[12], columns[14].strip()
            if not code or not name:
                continue
            concepts[code]["ttys"].add(tty)
            concepts[code]["names"].append(name)
    return dict(concepts)


def _strength_matches(names: list[str], spec: dict[str, Any]) -> bool:
    wanted_amount, wanted_unit = spec["amount"], spec["unit"]
    for name in names:
        for amount_text, unit in re.findall(
            r"(\d+(?:\.\d+)?)\s*(MCG|MG|G|UNIT)\b", name, flags=re.IGNORECASE
        ):
            amount = float(amount_text)
            unit = unit.casefold()
            if unit == "g":
                amount *= 1000
                unit = "mg"
            if unit == wanted_unit and abs(amount - wanted_amount) < 1e-9:
                return True
    return False


def _route_and_form_match(names: list[str], spec: dict[str, Any]) -> bool:
    joined = " ".join(norm(name) for name in names)
    if "injection" in spec["routes"] and "injection" not in joined:
        return False
    if "oral" in spec["routes"] and "oral" not in joined:
        return False
    if "tablet" in spec["forms"] and "tablet" not in joined:
        return False
    if "capsule" in spec["forms"] and "capsule" not in joined:
        return False
    return True


def _has_unmentioned_combination(names: list[str], mention: str) -> bool:
    if " / " not in " ".join(names):
        return False
    value = norm(mention)
    return "/" not in value and " và " not in f" {value} "


def select_structured_product(
    entity: Entity,
    concepts: dict[str, dict[str, Any]],
    unique_brands: dict[str, str],
) -> tuple[str, dict[str, Any]] | None:
    if entity.type != "THUỐC" or len(entity.candidates or []) != 1:
        return None
    old_code = entity.candidates[0]
    old = concepts.get(old_code)
    if not old or not (set(old["ttys"]) & CURRENT_TTYS):
        return None
    spec = parse_strength_and_form(entity.text)
    if spec is None:
        return None

    mention = norm(entity.text)
    brand_hits = [
        (len(alias), alias, code)
        for alias, code in unique_brands.items()
        if re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", mention)
    ]
    brand = max(brand_hits, default=None)
    old_identity_names = [norm(name) for name in old["names"] if set(old["ttys"]) & CURRENT_TTYS]
    identity = max(old_identity_names, key=len, default="")

    def eligible(code: str, row: dict[str, Any], tty: str) -> bool:
        if tty not in row["ttys"]:
            return False
        names = row["names"]
        joined = " ".join(norm(name) for name in names)
        if brand:
            brand_alias = brand[1]
            if tty == "SBD" and brand_alias not in joined:
                return False
            if tty == "SCD" and brand_alias in joined:
                return False
            if tty == "SCD" and identity and identity not in joined:
                return False
        elif identity and identity not in joined:
            return False
        if not _strength_matches(names, spec):
            return False
        if not _route_and_form_match(names, spec):
            return False
        if _has_unmentioned_combination(names, entity.text):
            return False
        return code != old_code

    if brand:
        branded = sorted(code for code, row in concepts.items() if eligible(code, row, "SBD"))
        if len(branded) == 1:
            return branded[0], {**spec, "identity": brand[1], "product_tty": "SBD"}
    generic = sorted(code for code, row in concepts.items() if eligible(code, row, "SCD"))
    if len(generic) == 1:
        return generic[0], {**spec, "identity": identity, "product_tty": "SCD"}
    return None


def build_structured_product_submission(
    input_dir: str | Path,
    baseline_dir: str | Path,
    output_dir: str | Path,
    conso_path: str | Path,
    unique_brands: dict[str, str],
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
    concepts = load_concepts(conso_path)
    changes: list[dict[str, Any]] = []

    for text_path in sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem)):
        raw = text_path.read_text(encoding="utf-8")
        source_path = baseline / f"{text_path.stem}.json"
        source = json.loads(source_path.read_text(encoding="utf-8"))
        entities = entities_from_json(source)
        validate_entities(entities, raw)
        for index, entity in enumerate(entities):
            selected = select_structured_product(entity, concepts, unique_brands)
            if selected is None:
                continue
            new_code, evidence = selected
            old = list(entity.candidates or [])
            entity.candidates = [new_code]
            changes.append({
                "record": int(text_path.stem), "entity_index": index,
                "text": entity.text, "position": list(entity.position),
                "old_candidates": old, "new_candidates": [new_code],
                "evidence": {
                    **evidence,
                    "routes": sorted(evidence["routes"]),
                    "forms": sorted(evidence["forms"]),
                },
            })
        transformed = [entity.to_dict() for entity in entities]
        for before, after in zip(source, transformed):
            for key in set(before) | set(after):
                if key != "candidates" and before.get(key) != after.get(key):
                    raise AssertionError(f"frozen field changed: {key}")
            if before.get("type") != "THUỐC" and before.get("candidates") != after.get("candidates"):
                raise AssertionError("non-drug candidate changed")
        validate_entities(entities, raw)
        (output / source_path.name).write_text(dumps_btc(transformed), encoding="utf-8")

    validation = validate_output_dir(inputs, output)
    new_codes = {row["new_candidates"][0] for row in changes}
    gates = {
        "changed_rows_ge_5": len(changes) >= 5,
        "changed_rows_le_20": len(changes) <= 20,
        "changed_records_ge_4": len({row["record"] for row in changes}) >= 4,
        "all_new_codes_active_tty_scd_or_sbd": all(
            code in concepts and bool(set(concepts[code]["ttys"]) & PRODUCT_TTYS)
            for code in new_codes
        ),
        "explicit_field_contradictions_zero": all(
            parse_strength_and_form(row["text"]) is not None for row in changes
        ),
        "extra_ingredient_contradictions_zero": all(
            not _has_unmentioned_combination(concepts[row["new_candidates"][0]]["names"], row["text"])
            for row in changes
        ),
        "all_100_records_validate": validation["ok"] and validation["records"] == 100,
    }
    if not all(gates.values()):
        raise RuntimeError(f"H70 gates failed: {gates}")
    package_output(output, target_zip, inputs)
    repeat = report_target.parent / "repeat.zip"
    package_output(output, repeat, inputs)
    deterministic = target_zip.read_bytes() == repeat.read_bytes()
    repeat.unlink()
    if not deterministic:
        raise RuntimeError("ZIP packaging is not deterministic")
    report = {
        "hypothesis": "H70_rxnorm_structured_product_identity",
        "status": "PASS_AWAITING_SUBMISSION_APPROVAL",
        "baseline_zip_sha256": EXPECTED_H69_SHA256,
        "zip": str(target_zip), "zip_sha256": sha256(target_zip),
        "zip_bytes": target_zip.stat().st_size,
        "changed_rows": len(changes),
        "changed_records": len({row["record"] for row in changes}),
        "gates": {**gates, "deterministic_zip_bytes": deterministic},
        "validation": validation, "changes": changes,
    }
    report_target.parent.mkdir(parents=True, exist_ok=True)
    report_target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
