"""Minimum-epoch recovery of H32's collapsed fold for H34."""

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
from .train import train_model
from .weak_label_adapt import export_jsonl


def _signature(rows: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    return sorted((row["record"], *row["position"], row["type"],
                   round(row["confidence"], 8)) for row in rows)


def run_experiment(input_dir: str | Path, label_dir: str | Path,
                   base_model: str | Path, h33_predictions: str | Path,
                   output_dir: str | Path, h20_dir: str | Path,
                   vietmed_dir: str | Path) -> dict[str, Any]:
    folds = make_folds()
    index = 3
    inference_records = folds[index]
    validation_records = folds[(index + 1) % 5]
    training_records = sorted(set(range(1, 101)) - set(inference_records) - set(validation_records))
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    export_jsonl(input_dir, label_dir, training_records, output / "train.jsonl")
    export_jsonl(input_dir, label_dir, validation_records, output / "dev.jsonl")
    checkpoint = Path("models/h34-minimum-epoch-fold3")
    training = train_model(
        output / "train.jsonl", checkpoint, base_model,
        epochs=8, max_length=256, learning_rate=2e-5, stride=64,
        batch_size=4, gradient_accumulation=4, seed=4334, patience=2,
        minimum_epochs=5, validation_path=output / "dev.jsonl", class_weighting=True,
    )
    validation_rows, validation_errors = collect_predictions(
        checkpoint, input_dir, validation_records)
    validation_gold = load_gold(label_dir, validation_records)
    grid = [threshold_metrics(validation_rows, validation_gold, threshold)
            for threshold in THRESHOLDS]
    selected = select_threshold(grid)
    first, first_errors = collect_predictions(checkpoint, input_dir, inference_records)
    second, second_errors = collect_predictions(checkpoint, input_dir, inference_records)
    accepted = ([row for row in first if row["confidence"] >= selected["threshold"]]
                if selected else [])
    fold = (threshold_metrics(first, load_gold(label_dir, inference_records),
                              selected["threshold"])
            if selected else None)
    fold_gates = {
        "eligible_nonempty_validation_threshold": selected is not None and selected["predicted"] > 0,
        "inference_precision_at_least_0_75": fold is not None and fold["precision"] >= 0.75,
        "inference_f1_at_least_0_50": fold is not None and fold["f1"] >= 0.50,
        "inference_recall_at_least_0_40": fold is not None and fold["recall"] >= 0.40,
        "deterministic_inference": _signature(first) == _signature(second),
        "offset_errors_equal_0": validation_errors == first_errors == second_errors == 0,
    }
    frozen = json.loads(Path(h33_predictions).read_text(encoding="utf-8"))
    combined = [row for row in frozen if int(row["record"]) not in inference_records] + accepted
    aggregate = {**_prf({_key(row) for row in combined},
                        load_gold(label_dir, range(1, 101))),
                 "predicted": len(combined)}
    aggregate_gates = {
        "precision_at_least_0_78": aggregate["precision"] >= 0.78,
        "f1_at_least_0_55": aggregate["f1"] >= 0.55,
        "recall_at_least_0_40": aggregate["recall"] >= 0.40,
        "every_fold_nonempty": bool(accepted),
    }
    agreements = None
    if all(fold_gates.values()) and all(aggregate_gates.values()):
        agreements = agreement_queue(combined, input_dir, label_dir, h20_dir, vietmed_dir)
        (output / "agreement_queue.json").write_text(
            json.dumps(agreements, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "combined_oof_predictions.json").write_text(
        json.dumps(combined, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {"training": training, "validation_grid": grid,
              "selected": selected, "fold": fold, "fold_gates": fold_gates,
              "aggregate": aggregate, "aggregate_gates": aggregate_gates,
              "agreements": ({key: value for key, value in agreements.items() if key != "queue"}
                             if agreements else None),
              "status": ("passed" if all(fold_gates.values()) and
                          all(aggregate_gates.values()) else "failed")}
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="turn2/input")
    parser.add_argument("--labels", default="turn2/output_v8_candidate_semantic")
    parser.add_argument("--base", default="models/bami-airace-v15-weighted")
    parser.add_argument("--h33", default="experiments/H33_per_fold_confidence_calibration/results/oof_predictions.json")
    parser.add_argument("--output", default="experiments/H34_minimum_epoch_recovery/results")
    parser.add_argument("--h20", default="turn2/output_v6_expanded_pair")
    parser.add_argument("--vietmed", default="experiments/H_turn2_multimodel_core/proposals_vietmed")
    args = parser.parse_args()
    print(json.dumps(run_experiment(args.input, args.labels, args.base, args.h33,
                                    args.output, args.h20, args.vietmed),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
