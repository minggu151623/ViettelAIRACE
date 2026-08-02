from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .ontology_dense import _metric_block


TYPE_SOURCE = {"CHẨN_ĐOÁN": "qwen", "THUỐC": "lexical"}


def type_specialist_fusion(
    dataset: dict[str, Any],
    lexical_report: dict[str, Any],
    qwen_report: dict[str, Any],
) -> dict[str, Any]:
    rows = dataset["rows"]
    lexical = {prediction["id"]: prediction["top10"] for prediction in lexical_report["predictions"]}
    qwen = {prediction["id"]: prediction["top10"] for prediction in qwen_report["predictions"]}
    expected = {row["id"] for row in rows}
    if set(lexical) != expected or set(qwen) != expected:
        raise ValueError("source reports do not cover the same dataset rows")
    rankings: list[list[str]] = []
    predictions: list[dict[str, Any]] = []
    for row in rows:
        source = TYPE_SOURCE[row["type"]]
        ranked = qwen[row["id"]] if source == "qwen" else lexical[row["id"]]
        rankings.append(ranked)
        predictions.append(
            {
                "id": row["id"],
                "fold": row["fold"],
                "type": row["type"],
                "source": source,
                "gold": row["gold_concepts"],
                "top10": ranked,
            }
        )
    report: dict[str, Any] = {
        "method": "fixed_type_specialist_router",
        "weak_label_warning": dataset["label_status"],
        "router": TYPE_SOURCE,
        "learned_parameters": 0,
        "all": _metric_block(rows, rankings),
        "folds": {},
        "predictions": predictions,
    }
    for fold in ("train", "dev", "test"):
        indices = [index for index, row in enumerate(rows) if row["fold"] == fold]
        report["folds"][fold] = _metric_block(
            [rows[index] for index in indices], [rankings[index] for index in indices]
        )
    return report


def save_fusion_report(report: dict[str, Any], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
