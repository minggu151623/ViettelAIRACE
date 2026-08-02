"""Frozen entity-confidence calibration for H31."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import torch
from transformers import AutoModelForTokenClassification

from .proposal_pu import DEFAULT_DEV, DEFAULT_TEST, _prf
from .train import _load_fast_tokenizer, predict_token_entities


THRESHOLDS = (0.50, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95)


def collect_predictions(checkpoint: str | Path, input_dir: str | Path,
                        records: Iterable[int]) -> tuple[list[dict[str, Any]], int]:
    device = torch.device("mps" if torch.backends.mps.is_available() else
                          "cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = _load_fast_tokenizer(checkpoint)
    model = AutoModelForTokenClassification.from_pretrained(str(checkpoint)).to(device)
    rows: list[dict[str, Any]] = []
    errors = 0
    for record in sorted(records):
        raw = (Path(input_dir) / f"{record}.txt").read_text(encoding="utf-8")
        for entity in predict_token_entities(raw, model=model, tokenizer=tokenizer,
                                             device=device, max_length=256, stride=64):
            start, end = entity.position
            errors += int(raw[start:end] != entity.text)
            rows.append({"record": record, "position": [start, end],
                         "type": entity.type, "text": entity.text,
                         "confidence": float(entity.confidence or 0.0)})
    return rows, errors


def load_gold(label_dir: str | Path, records: Iterable[int]) -> set[tuple[int, int, str, int]]:
    values = set()
    for record in sorted(records):
        for entity in json.loads((Path(label_dir) / f"{record}.json").read_text(encoding="utf-8")):
            start, end = entity["position"]
            values.add((int(start), int(end), str(entity["type"]), record))
    return values


def threshold_metrics(rows: list[dict[str, Any]], gold: set[tuple[int, int, str, int]],
                      threshold: float) -> dict[str, Any]:
    predicted = {(row["position"][0], row["position"][1], row["type"], row["record"])
                 for row in rows if row["confidence"] >= threshold}
    return {"threshold": threshold, **_prf(predicted, gold), "predicted": len(predicted)}


def select_threshold(grid: list[dict[str, Any]]) -> dict[str, Any] | None:
    eligible = [row for row in grid if row["precision"] >= 0.80]
    if not eligible:
        return None
    return max(eligible, key=lambda row: (row["f1"], row["precision"], row["threshold"]))


def dev_gates(selected: dict[str, Any] | None, offset_errors: int) -> dict[str, bool]:
    return {
        "eligible_threshold_exists": selected is not None,
        "precision_at_least_0_80": selected is not None and selected["precision"] >= 0.80,
        "strict_f1_at_least_0_60": selected is not None and selected["f1"] >= 0.60,
        "recall_at_least_0_45": selected is not None and selected["recall"] >= 0.45,
        "offset_errors_equal_0": offset_errors == 0,
    }


def run_experiment(checkpoint: str | Path, input_dir: str | Path,
                   label_dir: str | Path, output_dir: str | Path) -> dict[str, Any]:
    dev_rows, dev_errors = collect_predictions(checkpoint, input_dir, DEFAULT_DEV)
    dev_gold = load_gold(label_dir, DEFAULT_DEV)
    grid = [threshold_metrics(dev_rows, dev_gold, threshold) for threshold in THRESHOLDS]
    selected = select_threshold(grid)
    gates = dev_gates(selected, dev_errors)
    report: dict[str, Any] = {"dev_grid": grid, "selected": selected,
                             "dev_offset_errors": dev_errors, "dev_gates": gates,
                             "test": None, "test_gates": None,
                             "status": "dev_failed_test_canceled"}
    if all(gates.values()) and selected is not None:
        first, test_errors = collect_predictions(checkpoint, input_dir, DEFAULT_TEST)
        second, second_errors = collect_predictions(checkpoint, input_dir, DEFAULT_TEST)
        gold = load_gold(label_dir, DEFAULT_TEST)
        test = threshold_metrics(first, gold, selected["threshold"])
        signature = lambda rows: sorted((row["record"], *row["position"], row["type"],
                                         round(row["confidence"], 8)) for row in rows)
        final = {
            "precision_at_least_0_78": test["precision"] >= 0.78,
            "strict_f1_at_least_0_55": test["f1"] >= 0.55,
            "recall_at_least_0_40": test["recall"] >= 0.40,
            "deterministic_predictions": signature(first) == signature(second),
            "offset_errors_equal_0": test_errors == second_errors == 0,
        }
        report.update({"test": test, "test_gates": final,
                       "status": "passed" if all(final.values()) else "test_failed"})
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", default="models/h30-bami-weak-label")
    parser.add_argument("--input", default="turn2/input")
    parser.add_argument("--labels", default="turn2/output_v8_candidate_semantic")
    parser.add_argument("--output", default="experiments/H31_h30_confidence_calibration/results")
    args = parser.parse_args()
    print(json.dumps(run_experiment(args.checkpoint, args.input, args.labels, args.output),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
