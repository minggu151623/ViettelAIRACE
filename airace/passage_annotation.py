"""Prediction-blind repeated-passage annotation utilities for H41."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .repeated_passage_consistency import Occurrence, repeated_lines
from .schema import ASSERTIONS, CANDIDATE_TYPES, ENTITY_TYPES


EXPECTED_INPUT_SHA256 = "d68702073a5e478df60ab389b71587813ffac08475902f043446346ef0f15bcf"
SEED = "4101"
STRATA = {
    "high": {"count": 13, "holdout": 3},
    "middle": {"count": 17, "holdout": 5},
    "low": {"count": 30, "holdout": 7},
}


def _tree_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(value for value in path.rglob("*") if value.is_file()):
        digest.update(str(item.relative_to(path)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(item.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _passage_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _seeded_hash(passage_id: str) -> str:
    return hashlib.sha256(f"{SEED}{passage_id}".encode("utf-8")).hexdigest()


def _stratum(occurrences: list[Occurrence]) -> str:
    count = len({item.record for item in occurrences})
    if count >= 4:
        return "high"
    if count == 3:
        return "middle"
    return "low"


def build_manifest(input_dir: Path, output_path: Path) -> dict[str, Any]:
    observed_hash = _tree_digest(input_dir)
    if observed_hash != EXPECTED_INPUT_SHA256:
        raise ValueError(
            f"H41 input hash mismatch: expected {EXPECTED_INPUT_SHA256}, "
            f"observed {observed_hash}"
        )
    groups = repeated_lines(input_dir, minimum=40)
    by_stratum: dict[str, list[tuple[str, list[Occurrence]]]] = defaultdict(list)
    for text, occurrences in groups.items():
        by_stratum[_stratum(occurrences)].append((text, occurrences))

    passages: list[dict[str, Any]] = []
    for stratum, policy in STRATA.items():
        ranked = sorted(
            by_stratum[stratum],
            key=lambda item: (
                -len(item[0]) * len({value.record for value in item[1]}),
                _seeded_hash(_passage_id(item[0])),
            ),
        )[: policy["count"]]
        if len(ranked) != policy["count"]:
            raise ValueError(
                f"H41 stratum {stratum} has {len(ranked)} passages, "
                f"expected {policy['count']}"
            )
        split_order = sorted(
            ranked, key=lambda item: _seeded_hash(_passage_id(item[0]))
        )
        holdout_ids = {
            _passage_id(text) for text, _ in split_order[: policy["holdout"]]
        }
        for text, occurrences in ranked:
            passage_id = _passage_id(text)
            rows = [
                {"record_id": str(item.record), "position": [item.start, item.end]}
                for item in sorted(occurrences)
            ]
            passages.append(
                {
                    "passage_id": passage_id,
                    "stratum": stratum,
                    "split": "holdout" if passage_id in holdout_ids else "development",
                    "text": text,
                    "length": len(text),
                    "distinct_record_count": len({item.record for item in occurrences}),
                    "occurrences": rows,
                }
            )
    passages.sort(key=lambda row: (row["split"], row["stratum"], row["passage_id"]))
    manifest = {
        "version": 1,
        "protocol": "H41_repeated_passage_blind_annotation",
        "input_tree_sha256": observed_hash,
        "selection_seed": int(SEED),
        "passage_count": len(passages),
        "development_count": sum(row["split"] == "development" for row in passages),
        "holdout_count": sum(row["split"] == "holdout" for row in passages),
        "passages": passages,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def build_secondary_manifest(
    primary_manifest_path: Path, output_path: Path
) -> dict[str, Any]:
    """Create the 15-row blind double-annotation queue without split labels."""
    primary = json.loads(primary_manifest_path.read_text(encoding="utf-8"))
    passages = []
    for source in primary["passages"]:
        if source["split"] != "holdout":
            continue
        row = dict(source)
        row.pop("split", None)
        passages.append(row)
    result = {
        "version": primary["version"],
        "protocol": primary["protocol"],
        "input_tree_sha256": primary["input_tree_sha256"],
        "selection_seed": primary["selection_seed"],
        "passage_count": len(passages),
        "role": "independent_double_annotation",
        "passages": passages,
    }
    if len(passages) != 15:
        raise ValueError(f"Expected 15 secondary passages, found {len(passages)}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def load_labels(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {str(row["passage_id"]): row for row in rows}


def save_label(path: Path, row: dict[str, Any]) -> None:
    rows = load_labels(path)
    rows[str(row["passage_id"])] = row
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n"
            for _, value in sorted(rows.items())
        ),
        encoding="utf-8",
    )


def validate_passage_entities(text: str, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    occupied: set[tuple[int, int, str]] = set()
    for index, entity in enumerate(entities, 1):
        kind = str(entity.get("type") or "").strip()
        mention = str(entity.get("text") or "")
        position = entity.get("position") or [-1, -1]
        if kind not in ENTITY_TYPES:
            raise ValueError(f"Entity {index}: invalid type {kind!r}")
        if len(position) != 2:
            raise ValueError(f"Entity {index}: position must have two integers")
        start, end = int(position[0]), int(position[1])
        if not (0 <= start < end <= len(text)) or text[start:end] != mention:
            raise ValueError(f"Entity {index}: relative offset does not round-trip")
        key = (start, end, kind)
        if key in occupied:
            raise ValueError(f"Entity {index}: duplicate span/type")
        occupied.add(key)
        candidates = [str(value).strip() for value in entity.get("candidates", []) if str(value).strip()]
        row: dict[str, Any] = {
            "text": mention,
            "type": kind,
            "position": [start, end],
        }
        if kind in CANDIDATE_TYPES:
            row["candidates"] = list(dict.fromkeys(candidates))
        elif candidates:
            raise ValueError(f"Entity {index}: candidates are forbidden for {kind}")
        cleaned.append(row)
    cleaned.sort(key=lambda row: (row["position"], row["type"]))
    return cleaned


def validate_occurrence_assertions(
    entities: list[dict[str, Any]], occurrence_assertions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    cleaned: list[dict[str, Any]] = []
    seen: set[tuple[str, int, int, int]] = set()
    for row in occurrence_assertions:
        record_id = str(row["record_id"])
        occurrence = [int(value) for value in row["occurrence_position"]]
        entity_index = int(row["entity_index"])
        if not 0 <= entity_index < len(entities):
            raise ValueError(f"Invalid entity_index {entity_index}")
        assertions = [str(value).strip() for value in row.get("assertions", []) if str(value).strip()]
        invalid = set(assertions) - ASSERTIONS
        if invalid:
            raise ValueError(f"Invalid assertions: {sorted(invalid)}")
        key = (record_id, occurrence[0], occurrence[1], entity_index)
        if key in seen:
            raise ValueError(f"Duplicate occurrence assertion row: {key}")
        seen.add(key)
        cleaned.append(
            {
                "record_id": record_id,
                "occurrence_position": occurrence,
                "entity_index": entity_index,
                "assertions": list(dict.fromkeys(assertions)),
            }
        )
    cleaned.sort(
        key=lambda row: (
            int(row["record_id"]), row["occurrence_position"], row["entity_index"]
        )
    )
    return cleaned


def validate_annotation_file(
    manifest_path: Path, labels_path: Path, require_complete: bool = False
) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    labels = load_labels(labels_path)
    errors: list[str] = []
    completed_a = completed_b = 0
    manifest_ids = {row["passage_id"] for row in manifest["passages"]}
    for unknown in sorted(set(labels) - manifest_ids):
        errors.append(f"Unknown passage_id: {unknown}")
    for passage in manifest["passages"]:
        row = labels.get(passage["passage_id"])
        if row is None:
            if require_complete:
                errors.append(f"Missing passage: {passage['passage_id']}")
            continue
        try:
            if not str(row.get("reviewer_id") or "").strip():
                raise ValueError("reviewer_id is required")
            if row.get("passage_sha256") != passage["passage_id"]:
                raise ValueError("passage checksum mismatch")
            entities = validate_passage_entities(passage["text"], row.get("entities", []))
            assertions = validate_occurrence_assertions(
                entities, row.get("occurrence_assertions", [])
            )
            expected = {
                (item["record_id"], *item["position"], entity_index)
                for item in passage["occurrences"]
                for entity_index in range(len(entities))
            }
            observed = {
                (item["record_id"], *item["occurrence_position"], item["entity_index"])
                for item in assertions
            }
            if row.get("stage_a_reviewed"):
                completed_a += 1
            if row.get("stage_b_reviewed"):
                if observed != expected:
                    raise ValueError(
                        f"stage B coverage mismatch: expected {len(expected)}, got {len(observed)}"
                    )
                completed_b += 1
            if require_complete and not row.get("stage_a_reviewed"):
                raise ValueError("stage A is not marked reviewed")
            if require_complete and not row.get("stage_b_reviewed"):
                raise ValueError("stage B is not marked reviewed")
        except Exception as exc:
            errors.append(f"{passage['passage_id']}: {exc}")
    report = {
        "status": "valid" if not errors else "invalid",
        "passage_count": len(manifest["passages"]),
        "label_rows": len(labels),
        "stage_a_complete": completed_a,
        "stage_b_complete": completed_b,
        "errors": errors,
    }
    if errors:
        raise ValueError(json.dumps(report, ensure_ascii=False))
    return report


def context_for_occurrence(input_dir: Path, occurrence: dict[str, Any], radius: int = 200) -> str:
    raw = (input_dir / f"{occurrence['record_id']}.txt").read_text(encoding="utf-8")
    start, end = occurrence["position"]
    return (
        raw[max(0, start - radius):start]
        + "\n<<< ĐOẠN CẦN GÁN ASSERTION >>>\n"
        + raw[start:end]
        + "\n<<< HẾT ĐOẠN >>>\n"
        + raw[end:min(len(raw), end + radius)]
    )


def audit_manifest(input_dir: Path, manifest_path: Path) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    passages = manifest.get("passages", [])
    strata = {
        name: sum(row.get("stratum") == name for row in passages) for name in STRATA
    }
    splits = {
        name: sum(row.get("split") == name for row in passages)
        for name in ("development", "holdout")
    }
    round_trip = True
    occurrence_count = 0
    for passage in passages:
        if _passage_id(passage["text"]) != passage["passage_id"]:
            round_trip = False
        for occurrence in passage["occurrences"]:
            raw = (input_dir / f"{occurrence['record_id']}.txt").read_text(encoding="utf-8")
            start, end = occurrence["position"]
            occurrence_count += 1
            if raw[start:end] != passage["text"]:
                round_trip = False
    gates = {
        "input_hash_matches": _tree_digest(input_dir) == EXPECTED_INPUT_SHA256,
        "exactly_60_unique_passages": len(passages) == len({row["passage_id"] for row in passages}) == 60,
        "registered_strata_match": strata == {
            name: policy["count"] for name, policy in STRATA.items()
        },
        "registered_splits_match": splits == {"development": 45, "holdout": 15},
        "all_occurrence_offsets_round_trip": round_trip,
    }
    return {
        "status": "passed" if all(gates.values()) else "failed",
        "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "passage_count": len(passages),
        "occurrence_count": occurrence_count,
        "annotated_character_count_before_projection": sum(row["length"] for row in passages),
        "projected_character_count": sum(
            row["length"] * len(row["occurrences"]) for row in passages
        ),
        "strata": strata,
        "splits": splits,
        "gates": gates,
    }


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)


def reviewer_agreement(
    primary_manifest_path: Path,
    secondary_manifest_path: Path,
    primary_labels_path: Path,
    secondary_labels_path: Path,
) -> dict[str, Any]:
    primary_manifest = json.loads(primary_manifest_path.read_text(encoding="utf-8"))
    secondary_manifest = json.loads(secondary_manifest_path.read_text(encoding="utf-8"))
    primary = load_labels(primary_labels_path)
    secondary = load_labels(secondary_labels_path)
    selected_ids = {row["passage_id"] for row in secondary_manifest["passages"]}
    passage_by_id = {row["passage_id"]: row for row in primary_manifest["passages"]}
    missing_primary = sorted(selected_ids - set(primary))
    missing_secondary = sorted(selected_ids - set(secondary))
    if missing_primary or missing_secondary:
        raise ValueError(
            f"Incomplete reviewer labels: primary={len(missing_primary)}, "
            f"secondary={len(missing_secondary)}"
        )

    span_primary: set[tuple[str, int, int, str]] = set()
    span_secondary: set[tuple[str, int, int, str]] = set()
    assertion_primary: dict[tuple[str, str, int, int, int, int, str], set[str]] = {}
    assertion_secondary: dict[tuple[str, str, int, int, int, int, str], set[str]] = {}
    candidate_primary: dict[tuple[str, int, int, str], set[str]] = {}
    candidate_secondary: dict[tuple[str, int, int, str], set[str]] = {}

    for passage_id in sorted(selected_ids):
        passage = passage_by_id[passage_id]
        for target, spans, assertions, candidates in (
            (primary[passage_id], span_primary, assertion_primary, candidate_primary),
            (secondary[passage_id], span_secondary, assertion_secondary, candidate_secondary),
        ):
            entities = validate_passage_entities(passage["text"], target.get("entities", []))
            assertion_rows = validate_occurrence_assertions(
                entities, target.get("occurrence_assertions", [])
            )
            for entity in entities:
                key = (passage_id, entity["position"][0], entity["position"][1], entity["type"])
                spans.add(key)
                if entity["type"] in CANDIDATE_TYPES:
                    candidates[key] = set(entity.get("candidates", []))
            for row in assertion_rows:
                entity = entities[row["entity_index"]]
                key = (
                    passage_id,
                    row["record_id"],
                    row["occurrence_position"][0],
                    row["occurrence_position"][1],
                    entity["position"][0],
                    entity["position"][1],
                    entity["type"],
                )
                assertions[key] = set(row["assertions"])

    true_positive = len(span_primary & span_secondary)
    precision = true_positive / len(span_secondary) if span_secondary else float(not span_primary)
    recall = true_positive / len(span_primary) if span_primary else float(not span_secondary)
    span_f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    assertion_keys = set(assertion_primary) | set(assertion_secondary)
    assertion_score = (
        sum(
            _jaccard(assertion_primary.get(key, set()), assertion_secondary.get(key, set()))
            if key in assertion_primary and key in assertion_secondary
            else 0.0
            for key in assertion_keys
        ) / len(assertion_keys)
        if assertion_keys
        else 1.0
    )
    candidate_keys = set(candidate_primary) | set(candidate_secondary)
    candidate_score = (
        sum(
            _jaccard(candidate_primary.get(key, set()), candidate_secondary.get(key, set()))
            if key in candidate_primary and key in candidate_secondary
            else 0.0
            for key in candidate_keys
        ) / len(candidate_keys)
        if candidate_keys
        else 1.0
    )
    gates = {
        "strict_span_type_F1_at_least_0_85": span_f1 >= 0.85,
        "assertion_macro_jaccard_at_least_0_80": assertion_score >= 0.80,
    }
    return {
        "status": "passed" if all(gates.values()) else "needs_adjudication",
        "passages_compared": len(selected_ids),
        "strict_span_type": {
            "primary_count": len(span_primary),
            "secondary_count": len(span_secondary),
            "exact_matches": true_positive,
            "precision_secondary_vs_primary": precision,
            "recall_secondary_vs_primary": recall,
            "F1": span_f1,
        },
        "assertion_macro_jaccard": assertion_score,
        "candidate_macro_jaccard_diagnostic_only": candidate_score,
        "gates": gates,
    }
