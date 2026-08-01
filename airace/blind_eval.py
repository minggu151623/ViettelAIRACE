from __future__ import annotations

import hashlib
import json
import random
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from .metrics import score_entities
from .schema import Entity, entities_from_json
from .validator import validate_entities


SEED = 298409
SPLITS = {"development", "holdout"}
METRIC_NAMES = ("text_score", "assertions_score", "candidates_score", "final_score")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _record_features(text: str) -> dict[str, int]:
    lines = text.splitlines()
    nonempty = [line for line in lines if line.strip()]
    return {
        "characters": len(text),
        "lines": len(lines),
        "nonempty_lines": len(nonempty),
        "numbered_sections": sum(
            bool(re.match(r"^\s*\d+[.)]\s*", line)) for line in lines
        ),
        "bullets": sum(
            bool(re.match(r"^\s*(?:[-*•]|\d+[.)])\s+", line)) for line in lines
        ),
        "colon_rows": sum(":" in line for line in nonempty),
    }


def corpus_fingerprint(input_dir: str | Path) -> tuple[str, list[dict[str, Any]]]:
    root = Path(input_dir)
    files = sorted(root.glob("*.txt"), key=lambda path: int(path.stem))
    if not files:
        raise ValueError(f"no input .txt files in {root}")
    digest = hashlib.sha256()
    records: list[dict[str, Any]] = []
    for path in files:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
        digest.update(path.stem.encode("ascii"))
        digest.update(b"\0")
        digest.update(raw)
        digest.update(b"\0")
        records.append(
            {
                "record_id": path.stem,
                "sha256": _sha256_bytes(raw),
                "features": _record_features(text),
            }
        )
    return digest.hexdigest(), records


def _blind_rank(seed: int, purpose: str, row: dict[str, Any]) -> str:
    value = f"{seed}:{purpose}:{row['record_id']}:{row['sha256']}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def build_calibration_manifest(
    input_dir: str | Path,
    output_path: str | Path,
    *,
    queue_size: int = 18,
    holdout_size: int = 6,
    strata: int = 6,
    seed: int = SEED,
) -> dict[str, Any]:
    fingerprint, rows = corpus_fingerprint(input_dir)
    if queue_size > len(rows):
        raise ValueError("queue size exceeds corpus size")
    if queue_size % strata:
        raise ValueError("queue size must be divisible by strata")
    if holdout_size != strata:
        raise ValueError("frozen design requires one holdout record per stratum")

    ordered = sorted(
        rows,
        key=lambda row: (row["features"]["characters"], int(row["record_id"])),
    )
    buckets: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for index, row in enumerate(ordered):
        stratum = min(strata - 1, index * strata // len(ordered))
        buckets[stratum].append(row)

    per_stratum = queue_size // strata
    selected: list[dict[str, Any]] = []
    for stratum in range(strata):
        candidates = sorted(
            buckets[stratum],
            key=lambda row: _blind_rank(seed, f"select-{stratum}", row),
        )
        chosen = candidates[:per_stratum]
        holdout = min(
            chosen,
            key=lambda row: _blind_rank(seed, f"split-{stratum}", row),
        )
        for row in chosen:
            selected.append(
                {
                    **row,
                    "stratum": stratum + 1,
                    "split": "holdout" if row is holdout else "development",
                }
            )

    selected.sort(key=lambda row: int(row["record_id"]))
    manifest = {
        "version": 1,
        "purpose": "prediction-blind Turn 2 promotion calibration",
        "input_dir": str(Path(input_dir)),
        "corpus_records": len(rows),
        "corpus_sha256": fingerprint,
        "seed": seed,
        "selection": {
            "queue_size": queue_size,
            "strata": strata,
            "stratification_key": "raw character count",
            "within_stratum": "seeded SHA-256 rank; no prediction features",
            "development_records": queue_size - holdout_size,
            "holdout_records": holdout_size,
        },
        "records": selected,
        "record_ids": {
            split: [row["record_id"] for row in selected if row["split"] == split]
            for split in ("development", "holdout")
        },
        "annotation_policy": [
            "Start from raw text and an empty prediction directory.",
            "Label exact spans and types; preserve repeated occurrences.",
            "Use assertions only with explicit section or local-scope evidence.",
            "Leave candidates empty unless independently defensible.",
        ],
        "status": "awaiting_blind_annotation",
    }
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def _load_manifest(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def verify_manifest(manifest: dict[str, Any], input_dir: str | Path) -> list[str]:
    fingerprint, rows = corpus_fingerprint(input_dir)
    errors: list[str] = []
    if fingerprint != manifest.get("corpus_sha256"):
        errors.append("corpus fingerprint differs from frozen manifest")
    current = {row["record_id"]: row["sha256"] for row in rows}
    for row in manifest.get("records", []):
        if current.get(str(row["record_id"])) != row.get("sha256"):
            errors.append(f"record {row['record_id']} differs from frozen manifest")
    return errors


def manifest_record_ids(
    manifest_path: str | Path, split: str = "all"
) -> list[str]:
    manifest = _load_manifest(manifest_path)
    if split == "all":
        return [str(row["record_id"]) for row in manifest["records"]]
    if split not in SPLITS:
        raise ValueError(f"unknown split: {split}")
    return [
        str(row["record_id"])
        for row in manifest["records"]
        if row["split"] == split
    ]


def _load_annotations(path: str | Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    source = Path(path)
    if not source.exists():
        return rows
    for line_number, line in enumerate(source.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        record_id = str(row["record_id"])
        if record_id in rows:
            raise ValueError(f"duplicate annotation for record {record_id}")
        if not row.get("reviewed"):
            raise ValueError(f"record {record_id} is not marked reviewed")
        rows[record_id] = row
    return rows


def _load_prediction(
    directory: Path, record_id: str, raw_text: str
) -> tuple[list[Entity], str | None]:
    path = directory / f"{record_id}.json"
    if not path.exists():
        return [], f"missing prediction {path}"
    try:
        entities = entities_from_json(json.loads(path.read_text(encoding="utf-8")))
        validate_entities(entities, raw_text)
        return entities, None
    except Exception as exc:
        return [], f"invalid prediction {path}: {exc}"


def _strict_keys(record_id: str, entities: Iterable[Entity]) -> set[tuple[str, int, int, str]]:
    return {
        (record_id, entity.position[0], entity.position[1], entity.type)
        for entity in entities
    }


def _prf(gold: set[Any], predicted: set[Any]) -> dict[str, float | int]:
    tp = len(gold & predicted)
    fp = len(predicted - gold)
    fn = len(gold - predicted)
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-12, precision + recall)
    return {
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "tp": tp,
        "fp": fp,
        "fn": fn,
    }


def _mean(values: Iterable[float]) -> float:
    materialized = list(values)
    return sum(materialized) / max(1, len(materialized))


def paired_bootstrap_interval(
    deltas: list[float], *, iterations: int = 10_000, seed: int = SEED
) -> dict[str, float | int]:
    if not deltas:
        raise ValueError("cannot bootstrap an empty delta list")
    rng = random.Random(seed)
    n = len(deltas)
    samples = sorted(
        sum(deltas[rng.randrange(n)] for _ in range(n)) / n
        for _ in range(iterations)
    )
    lower = samples[int(0.025 * (iterations - 1))]
    upper = samples[int(0.975 * (iterations - 1))]
    return {
        "iterations": iterations,
        "seed": seed,
        "mean": round(_mean(deltas), 6),
        "lower_95": round(lower, 6),
        "upper_95": round(upper, 6),
    }


def evaluate_blind_challenger(
    *,
    input_dir: str | Path,
    manifest_path: str | Path,
    labels_path: str | Path,
    baseline_dir: str | Path,
    challenger_dir: str | Path,
    split: str = "development",
    output_path: str | Path | None = None,
    bootstrap_iterations: int = 10_000,
    seed: int = SEED,
) -> dict[str, Any]:
    manifest = _load_manifest(manifest_path)
    manifest_errors = verify_manifest(manifest, input_dir)
    record_ids = manifest_record_ids(manifest_path, split)
    annotations = _load_annotations(labels_path)
    missing_annotations = [record_id for record_id in record_ids if record_id not in annotations]
    baseline_root = Path(baseline_dir)
    challenger_root = Path(challenger_dir)
    input_root = Path(input_dir)
    validation_errors: list[str] = list(manifest_errors)
    per_record: list[dict[str, Any]] = []
    strict_gold: set[Any] = set()
    strict_baseline: set[Any] = set()
    strict_challenger: set[Any] = set()

    for record_id in record_ids:
        if record_id in missing_annotations:
            continue
        raw_text = (input_root / f"{record_id}.txt").read_text(encoding="utf-8")
        annotation = annotations[record_id]
        if annotation.get("text") != raw_text:
            validation_errors.append(f"annotation text mismatch for record {record_id}")
            continue
        gold = entities_from_json(annotation.get("entities", []))
        try:
            validate_entities(gold, raw_text)
        except Exception as exc:
            validation_errors.append(f"invalid gold record {record_id}: {exc}")
            continue
        baseline, baseline_error = _load_prediction(baseline_root, record_id, raw_text)
        challenger, challenger_error = _load_prediction(challenger_root, record_id, raw_text)
        validation_errors.extend(
            error for error in (baseline_error, challenger_error) if error is not None
        )
        if baseline_error or challenger_error:
            continue
        baseline_scores = score_entities(gold, baseline)
        challenger_scores = score_entities(gold, challenger)
        deltas = {
            name: challenger_scores[name] - baseline_scores[name]
            for name in METRIC_NAMES
        }
        per_record.append(
            {
                "record_id": record_id,
                "baseline": {name: round(baseline_scores[name], 6) for name in METRIC_NAMES},
                "challenger": {name: round(challenger_scores[name], 6) for name in METRIC_NAMES},
                "delta": {name: round(deltas[name], 6) for name in METRIC_NAMES},
            }
        )
        strict_gold |= _strict_keys(record_id, gold)
        strict_baseline |= _strict_keys(record_id, baseline)
        strict_challenger |= _strict_keys(record_id, challenger)

    complete = not missing_annotations and not validation_errors and len(per_record) == len(record_ids)
    report: dict[str, Any] = {
        "split": split,
        "records_expected": len(record_ids),
        "records_evaluated": len(per_record),
        "complete": complete,
        "missing_annotations": missing_annotations,
        "validation_errors": validation_errors,
        "baseline_dir": str(baseline_root),
        "challenger_dir": str(challenger_root),
        "per_record": per_record,
    }
    if not complete:
        report["decision"] = "INCOMPLETE_ANNOTATIONS"
    else:
        means = {
            side: {
                name: round(_mean(row[side][name] for row in per_record), 6)
                for name in METRIC_NAMES
            }
            for side in ("baseline", "challenger")
        }
        delta_means = {
            name: round(_mean(row["delta"][name] for row in per_record), 6)
            for name in METRIC_NAMES
        }
        baseline_prf = _prf(strict_gold, strict_baseline)
        challenger_prf = _prf(strict_gold, strict_challenger)
        interval = paired_bootstrap_interval(
            [row["delta"]["final_score"] for row in per_record],
            iterations=bootstrap_iterations,
            seed=seed,
        )
        nonregression_rate = _mean(
            row["delta"]["final_score"] >= 0 for row in per_record
        )
        checks = {
            "final_delta_at_least_0_03": delta_means["final_score"] >= 0.03,
            "bootstrap_lower_bound_positive": interval["lower_95"] > 0,
            "strict_f1_non_decreasing": challenger_prf["f1"] >= baseline_prf["f1"],
            "component_floor": all(
                delta_means[name] >= -0.01
                for name in ("text_score", "assertions_score", "candidates_score")
            ),
            "record_nonregression_at_least_half": nonregression_rate >= 0.5,
        }
        report.update(
            {
                "mean_scores": means,
                "mean_delta": delta_means,
                "strict_span_type": {
                    "baseline": baseline_prf,
                    "challenger": challenger_prf,
                },
                "paired_bootstrap_final_delta": interval,
                "record_nonregression_rate": round(nonregression_rate, 6),
                "promotion_checks": checks,
            }
        )
        if split != "holdout":
            decision = "DEVELOPMENT_ONLY"
        elif all(checks.values()):
            decision = "PROMOTE"
        elif (
            delta_means["final_score"] <= 0
            or challenger_prf["f1"] < baseline_prf["f1"]
            or not checks["component_floor"]
        ):
            decision = "REJECT"
        else:
            decision = "INSUFFICIENT_EVIDENCE"
        report["decision"] = decision

    if output_path is not None:
        target = Path(output_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return report

