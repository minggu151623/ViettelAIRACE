"""Validation-calibrated frozen cross-fit checkpoints for H33."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .confidence_calibration import (
    THRESHOLDS,
    collect_predictions,
    load_gold,
    select_threshold,
    threshold_metrics,
)
from .crossfit_voter import _key, agreement_queue, make_folds
from .proposal_pu import _prf


def _signature(rows: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    return sorted((row["record"], *row["position"], row["type"],
                   round(row["confidence"], 8)) for row in rows)


def run_experiment(input_dir: str | Path, label_dir: str | Path,
                   checkpoint_pattern: str, output_dir: str | Path,
                   h20_dir: str | Path, vietmed_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    folds = make_folds()
    selected_rows: list[dict[str, Any]] = []
    fold_results = []
    eligible = True
    deterministic = True
    offset_errors = 0
    for index, inference_records in enumerate(folds):
        validation_records = folds[(index + 1) % 5]
        checkpoint = checkpoint_pattern.format(index=index)
        validation_rows, validation_errors = collect_predictions(
            checkpoint, input_dir, validation_records)
        offset_errors += validation_errors
        validation_gold = load_gold(label_dir, validation_records)
        grid = [threshold_metrics(validation_rows, validation_gold, value)
                for value in THRESHOLDS]
        selected = select_threshold(grid)
        if selected is None:
            eligible = False
            fold_results.append({"fold": index, "selected": None,
                                 "validation_grid": grid, "inference": None})
            continue
        first, first_errors = collect_predictions(checkpoint, input_dir, inference_records)
        second, second_errors = collect_predictions(checkpoint, input_dir, inference_records)
        offset_errors += first_errors + second_errors
        deterministic = deterministic and _signature(first) == _signature(second)
        threshold = selected["threshold"]
        accepted = [row for row in first if row["confidence"] >= threshold]
        selected_rows.extend(accepted)
        inference_gold = load_gold(label_dir, inference_records)
        metrics = threshold_metrics(first, inference_gold, threshold)
        fold_results.append({"fold": index, "selected": selected,
                             "validation_grid": grid, "inference": metrics,
                             "records": list(inference_records)})
        print(f"H33 fold {index + 1}/5 threshold={threshold:.2f} "
              f"precision={metrics['precision']:.4f} f1={metrics['f1']:.4f}", flush=True)
    gold = load_gold(label_dir, range(1, 101))
    aggregate = {**_prf({_key(row) for row in selected_rows}, gold),
                 "predicted": len(selected_rows), "offset_errors": offset_errors}
    nonempty_precisions = [row["inference"]["precision"] for row in fold_results
                           if row.get("inference") and row["inference"]["predicted"] > 0]
    gates = {
        "every_fold_has_eligible_threshold": eligible,
        "precision_at_least_0_78": aggregate["precision"] >= 0.78,
        "f1_at_least_0_55": aggregate["f1"] >= 0.55,
        "recall_at_least_0_40": aggregate["recall"] >= 0.40,
        "every_nonempty_fold_precision_at_least_0_70": all(value >= 0.70 for value in nonempty_precisions),
        "every_fold_emits_prediction": all(row.get("inference", {}).get("predicted", 0) > 0
                                           for row in fold_results),
        "offset_errors_equal_0": offset_errors == 0,
        "deterministic_second_inference": deterministic,
    }
    agreements = None
    if all(gates.values()):
        agreements = agreement_queue(selected_rows, input_dir, label_dir, h20_dir, vietmed_dir)
        (output / "agreement_queue.json").write_text(
            json.dumps(agreements, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "oof_predictions.json").write_text(
        json.dumps(selected_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {"folds": fold_results, "aggregate": aggregate, "gates": gates,
              "agreements": ({key: value for key, value in agreements.items() if key != "queue"}
                             if agreements else None),
              "status": "passed" if all(gates.values()) else "failed"}
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="turn2/input")
    parser.add_argument("--labels", default="turn2/output_v8_candidate_semantic")
    parser.add_argument("--checkpoints", default="models/h32-crossfit-{index}")
    parser.add_argument("--output", default="experiments/H33_per_fold_confidence_calibration/results")
    parser.add_argument("--h20", default="turn2/output_v6_expanded_pair")
    parser.add_argument("--vietmed", default="experiments/H_turn2_multimodel_core/proposals_vietmed")
    args = parser.parse_args()
    print(json.dumps(run_experiment(args.input, args.labels, args.checkpoints,
                                    args.output, args.h20, args.vietmed),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
