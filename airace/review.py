from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .metrics import score_entities
from .schema import entities_from_json


def _span_set(values: list[Any]) -> set[tuple[int, int, str]]:
    return {
        (entity.position[0], entity.position[1], entity.type)
        for entity in values
    }


def _prf(gold: set[Any], pred: set[Any]) -> dict[str, float | int]:
    tp = len(gold & pred)
    fp = len(pred - gold)
    fn = len(gold - pred)
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


def evaluate_reviewed(
    labels_path: str | Path, pred_dir: str | Path
) -> dict[str, Any]:
    rows = [
        json.loads(line)
        for line in Path(labels_path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    prediction_path = Path(pred_dir)
    all_gold: set[tuple[str, int, int, str]] = set()
    all_pred: set[tuple[str, int, int, str]] = set()
    per_type_gold: dict[str, set[tuple[str, int, int]]] = {}
    per_type_pred: dict[str, set[tuple[str, int, int]]] = {}
    metric_rows: list[dict[str, float]] = []
    missing: list[str] = []
    for row in rows:
        record_id = str(row["record_id"])
        path = prediction_path / f"{record_id}.json"
        if not path.exists():
            missing.append(record_id)
            predicted = []
        else:
            predicted = entities_from_json(json.loads(path.read_text(encoding="utf-8")))
        gold = entities_from_json(row.get("entities", []))
        for start, end, kind in _span_set(gold):
            all_gold.add((record_id, start, end, kind))
            per_type_gold.setdefault(kind, set()).add((record_id, start, end))
        for start, end, kind in _span_set(predicted):
            all_pred.add((record_id, start, end, kind))
            per_type_pred.setdefault(kind, set()).add((record_id, start, end))
        metric_rows.append(score_entities(gold, predicted))

    kinds = sorted(set(per_type_gold) | set(per_type_pred))
    averaged = {
        key: round(sum(row[key] for row in metric_rows) / max(1, len(metric_rows)), 6)
        for key in {
            "text_score",
            "assertions_score",
            "candidates_score",
            "final_score",
        }
    }
    return {
        "records": len(rows),
        "missing_predictions": missing,
        "strict_span_type": _prf(all_gold, all_pred),
        "per_type": {
            kind: _prf(
                per_type_gold.get(kind, set()),
                per_type_pred.get(kind, set()),
            )
            for kind in kinds
        },
        "competition_metric_reconstruction": averaged,
        "gold_entities": len(all_gold),
        "predicted_entities": len(all_pred),
    }
