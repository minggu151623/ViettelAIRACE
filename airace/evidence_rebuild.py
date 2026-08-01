from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from .assertions import attach_assertions
from .candidates import CandidateResolver
from .coordinates import project_entity_to_crlf
from .lab_splitter import find_numeric_lab_pairs
from .resources import load_lexicon
from .schema import Entity
from .serialization import dumps_btc
from .validator import validate_entities


POLICY_LAB_ALIASES = (
    "SpO2",
    "alt",
    "ast (aspartate aminotransferase)",
    "bilirubin toàn phần",
    "bilirubin toàn phần (tbili)",
    "bạch cầu",
    "ck",
    "cr (creatinine)",
    "creatinine",
    "glucose",
    "hemoglobin",
    "kali",
    "lactate",
    "neutrophil",
    "troponin",
)


def _entity_key(entity: Entity) -> tuple[int, int, str]:
    return (*entity.position, entity.type)


def split_numeric_labs(
    raw_text: str,
    entities: list[Entity],
    lab_names: list[str],
    stats: Counter[str] | None = None,
) -> list[Entity]:
    """Replace compound numeric lab-result spans with independent entities.

    The organiser's official example represents a test name and its numeric
    result as two entities. This function applies that policy only to
    high-precision name/value pairs found by ``find_numeric_lab_pairs``.
    """

    counts = stats if stats is not None else Counter()
    pairs = find_numeric_lab_pairs(raw_text, lab_names)
    if not pairs:
        return entities

    compound_result_indexes: set[int] = set()
    supported_pairs = set()
    for index, entity in enumerate(entities):
        if entity.type != "KẾT_QUẢ_XÉT_NGHIỆM":
            continue
        start, end = entity.position
        for pair in pairs:
            covers_name = start <= pair.name[0] and pair.name[1] <= end
            covers_result = start <= pair.result[0] and pair.result[1] <= end
            is_exact_result = entity.position == pair.result
            if covers_name and covers_result and not is_exact_result:
                compound_result_indexes.add(index)
                supported_pairs.add(pair)
                break

    # The independent-name/result policy supports adding further rows, but the
    # current research protocol deliberately changes only rows where the V6
    # source already emitted one compound result. This keeps the edit causal
    # and avoids converting treatment doses or vital signs into new labs.
    pairs = sorted(supported_pairs, key=lambda pair: (pair.name[0], pair.result[0]))
    if not pairs:
        return entities

    output = [
        entity for index, entity in enumerate(entities)
        if index not in compound_result_indexes
    ]
    counts["lab:removed_compound_results"] += len(compound_result_indexes)
    existing = {_entity_key(entity) for entity in output}

    for pair in pairs:
        name_key = (*pair.name, "TÊN_XÉT_NGHIỆM")
        if name_key not in existing:
            output.append(
                Entity(
                    text=raw_text[slice(*pair.name)],
                    type="TÊN_XÉT_NGHIỆM",
                    assertions=[],
                    position=pair.name,
                    candidates=None,
                    confidence=1.0,
                    source="evidence:official-lab-policy",
                )
            )
            existing.add(name_key)
            counts["lab:added_test_names"] += 1

        result_key = (*pair.result, "KẾT_QUẢ_XÉT_NGHIỆM")
        if result_key not in existing:
            output.append(
                Entity(
                    text=raw_text[slice(*pair.result)],
                    type="KẾT_QUẢ_XÉT_NGHIỆM",
                    assertions=[],
                    position=pair.result,
                    candidates=None,
                    confidence=1.0,
                    source="evidence:official-lab-policy",
                )
            )
            existing.add(result_key)
            counts["lab:added_numeric_results"] += 1

    counts["lab:detected_pairs"] += len(pairs)
    output.sort(key=lambda entity: (entity.position, entity.type))
    return output


def _refresh_drug_candidates(
    entities: list[Entity],
    raw_text: str,
    resolver: CandidateResolver,
    stats: Counter[str],
) -> None:
    for entity in entities:
        if entity.type != "THUỐC":
            continue
        before = tuple(entity.candidates or [])
        resolver.resolve(entity, raw_text)
        after = tuple(entity.candidates or [])
        if before != after:
            stats["rxnorm:changed_entities"] += 1
            if not before and after:
                stats["rxnorm:filled_candidates"] += 1
            elif before and not after:
                stats["rxnorm:abstained_candidates"] += 1
            else:
                stats["rxnorm:replaced_candidates"] += 1


def rebuild_with_evidence(
    input_dir: str | Path,
    source_dir: str | Path,
    output_dir: str | Path,
    report_path: str | Path | None = None,
    *,
    refresh_assertions: bool = False,
    refresh_rxnorm: bool = False,
    split_labs: bool = False,
    position_mode: str = "raw",
) -> dict[str, Any]:
    """Build a deterministic, auditable output from an externally scored source."""

    if position_mode not in {"raw", "crlf"}:
        raise ValueError(f"unsupported position mode: {position_mode}")
    if not any((refresh_assertions, refresh_rxnorm, split_labs, position_mode == "crlf")):
        raise ValueError("no evidence intervention selected")

    started = time.perf_counter()
    inputs = Path(input_dir)
    source = Path(source_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    records = sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem))
    expected_stems = {path.stem for path in records}
    extra_source = sorted(
        path.name for path in source.glob("*.json") if path.stem not in expected_stems
    )
    if extra_source:
        raise ValueError(f"unexpected JSON files in source: {extra_source}")

    lexicon = load_lexicon()
    lab_names = sorted(
        set(lexicon.get("lab_names", [])) | set(POLICY_LAB_ALIASES),
        key=str.casefold,
    )
    resolver = CandidateResolver() if refresh_rxnorm else None
    stats: Counter[str] = Counter()
    entity_counts: Counter[str] = Counter()
    errors: list[dict[str, str]] = []

    for text_path in records:
        stem = text_path.stem
        try:
            raw_text = text_path.read_text(encoding="utf-8")
            source_values = json.loads(
                (source / f"{stem}.json").read_text(encoding="utf-8")
            )
            source_entities = [Entity.from_dict(value) for value in source_values]
            validate_entities(source_entities, raw_text)
            entities = [Entity.from_dict(entity.to_dict()) for entity in source_entities]

            if split_labs:
                entities = split_numeric_labs(raw_text, entities, lab_names, stats)

            if refresh_assertions:
                before = [tuple(entity.assertions) for entity in entities]
                attach_assertions(entities, raw_text)
                stats["assertion:changed_entities"] += sum(
                    old != tuple(entity.assertions)
                    for old, entity in zip(before, entities)
                )

            if refresh_rxnorm:
                assert resolver is not None
                _refresh_drug_candidates(entities, raw_text, resolver, stats)

            entities.sort(key=lambda entity: (entity.position, entity.type))
            validate_entities(entities, raw_text)
            stats["source_entities"] += len(source_entities)
            stats["semantic_output_entities"] += len(entities)

            if position_mode == "crlf":
                projected = [
                    project_entity_to_crlf(raw_text, entity) for entity in entities
                ]
                stats["position:shifted_entities"] += sum(
                    before.position != after.position
                    for before, after in zip(entities, projected)
                )
                entities = projected
                validate_entities(entities, raw_text, position_mode="crlf")

            entity_counts.update(entity.type for entity in entities)
            serialized = dumps_btc([entity.to_dict() for entity in entities])
            if json.loads(serialized) != [entity.to_dict() for entity in entities]:
                raise ValueError("BTC serialization changed JSON values")
            (output / f"{stem}.json").write_text(serialized, encoding="utf-8")
            stats["completed_records"] += 1
        except Exception as exc:
            errors.append({"record": stem, "error": str(exc)})

    found_stems = {path.stem for path in output.glob("*.json")}
    unexpected_output = sorted(found_stems - expected_stems, key=str)
    missing_output = sorted(expected_stems - found_stems, key=lambda item: int(item))
    if unexpected_output:
        errors.append(
            {"record": "*", "error": f"unexpected output JSON files: {unexpected_output}"}
        )
    if missing_output:
        errors.append({"record": "*", "error": f"missing outputs: {missing_output}"})

    report = {
        "records": len(records),
        "completed": stats["completed_records"],
        "source": str(source),
        "output": str(output),
        "position_mode": position_mode,
        "interventions": {
            "refresh_assertions": refresh_assertions,
            "refresh_rxnorm": refresh_rxnorm,
            "split_numeric_labs": split_labs,
            "project_crlf_positions": position_mode == "crlf",
        },
        "entity_counts": dict(sorted(entity_counts.items())),
        "stats": dict(sorted(stats.items())),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "errors": errors,
        "offline": True,
    }
    if report_path:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return report
