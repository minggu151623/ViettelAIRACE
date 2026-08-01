"""Calibrate a proposal confidence threshold on the held-out source split."""
from __future__ import annotations

import json
from pathlib import Path

from airace.schema import entities_from_json
from airace.train import _prf, _strict_span_set, predict_token_entities


ROOT = Path(__file__).resolve().parents[3]
VALIDATION = ROOT / "data" / "vietbioner_transfer" / "valid.jsonl"
CHECKPOINT = ROOT / "models" / "vietbioner-diagnostic-bami"
OUTPUT = ROOT / "experiments" / "H_public_supervised_transfer" / "results" / "threshold_calibration.json"
THRESHOLDS = [0.0, 0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95]


def main() -> None:
    rows = [json.loads(line) for line in VALIDATION.read_text(encoding="utf-8").splitlines()]
    predictions = [
        predict_token_entities(row["text"], checkpoint=CHECKPOINT, max_length=192, stride=48)
        for row in rows
    ]
    gold = [_strict_span_set(row["text"], entities_from_json(row["entities"])) for row in rows]
    scores = []
    for threshold in THRESHOLDS:
        predicted = [
            _strict_span_set(row["text"], [entity for entity in items if entity.confidence >= threshold])
            for row, items in zip(rows, predictions)
        ]
        scores.append({"threshold": threshold, **_prf(gold, predicted)})
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({"scores": scores}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"scores": scores}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
