"""Five-fold out-of-fold high-confidence token voter for H32."""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from .confidence_calibration import collect_predictions, load_gold
from .phrase_policy import build_lexicon, match_lexicon, select_disjoint
from .proposal_pu import DEFAULT_TRAIN, TYPE_ORDER, _prf
from .proposals import load_proposals
from .weak_label_adapt import export_jsonl
from .train import train_model


def make_folds(seed: int = 9191) -> list[tuple[int, ...]]:
    records = list(range(1, 101))
    random.Random(seed).shuffle(records)
    folds = [[] for _ in range(5)]
    for index, record in enumerate(records):
        folds[index % 5].append(record)
    return [tuple(sorted(fold)) for fold in folds]


def _key(row: dict[str, Any]) -> tuple[int, int, str, int]:
    return (int(row["position"][0]), int(row["position"][1]),
            str(row["type"]), int(row["record"]))


def _load_json_keys(root: str | Path, record: int) -> set[tuple[int, int, str, int]]:
    return {(int(row["position"][0]), int(row["position"][1]),
             str(row["type"]), record)
            for row in json.loads((Path(root) / f"{record}.json").read_text(encoding="utf-8"))}


def agreement_queue(rows: list[dict[str, Any]], input_dir: str | Path,
                    h23_dir: str | Path, h20_dir: str | Path,
                    vietmed_dir: str | Path) -> dict[str, Any]:
    lexicon = build_lexicon(h23_dir, DEFAULT_TRAIN, 2)
    h32 = {_key(row): row for row in rows}
    h23: set[tuple[int, int, str, int]] = set()
    phrases: set[tuple[int, int, str, int]] = set()
    vietmed: set[tuple[int, int, str, int]] = set()
    for record in range(1, 101):
        raw = (Path(input_dir) / f"{record}.txt").read_text(encoding="utf-8")
        h23.update(_load_json_keys(h23_dir, record))
        baseline = json.loads((Path(h20_dir) / f"{record}.json").read_text(encoding="utf-8"))
        selected = select_disjoint(
            match_lexicon(raw, record, lexicon, case_sensitive=False),
            [tuple(entity["position"]) for entity in baseline],
        )
        phrases.update((item.position[0], item.position[1], item.type, record)
                       for item in selected)
        vietmed.update((item.position[0], item.position[1], item.type, record)
                       for item in load_proposals(Path(vietmed_dir) / f"{record}.json"))
    novel = set(h32) - h23
    phrase_agree = novel & phrases
    vietmed_agree = novel & vietmed
    triple = phrase_agree & vietmed_agree
    queue = []
    for key in sorted(phrase_agree | vietmed_agree, key=lambda value: (value[3], value[0], value[1], value[2])):
        row = h32[key]
        raw = (Path(input_dir) / f"{key[3]}.txt").read_text(encoding="utf-8")
        start, end = key[0], key[1]
        queue.append({**row, "agrees_phrase": key in phrases,
                      "agrees_vietmed": key in vietmed,
                      "context": raw[max(0, start - 100):min(len(raw), end + 100)]})
    return {"h32_novel": len(novel), "h32_plus_phrase": len(phrase_agree),
            "h32_plus_vietmed": len(vietmed_agree), "three_source": len(triple),
            "queue": queue}


def run_experiment(input_dir: str | Path, label_dir: str | Path,
                   base_model: str | Path, output_dir: str | Path,
                   h20_dir: str | Path,
                   vietmed_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    folds = make_folds()
    all_rows: list[dict[str, Any]] = []
    fold_metrics = []
    offset_errors = 0
    for index, inference_records in enumerate(folds):
        validation_records = folds[(index + 1) % 5]
        train_records = sorted(set(range(1, 101)) - set(inference_records) - set(validation_records))
        fold_dir = output / f"fold_{index}"
        checkpoint = Path("models") / f"h32-crossfit-{index}"
        export_jsonl(input_dir, label_dir, train_records, fold_dir / "train.jsonl")
        export_jsonl(input_dir, label_dir, validation_records, fold_dir / "dev.jsonl")
        print(f"H32 fold {index + 1}/5 training", flush=True)
        training = train_model(
            fold_dir / "train.jsonl", checkpoint, base_model,
            epochs=8, max_length=256, learning_rate=2e-5, stride=64,
            batch_size=4, gradient_accumulation=4, seed=4331 + index,
            patience=2, validation_path=fold_dir / "dev.jsonl", class_weighting=True,
        )
        predicted, errors = collect_predictions(checkpoint, input_dir, inference_records)
        offset_errors += errors
        selected = [row for row in predicted if row["confidence"] >= 0.90]
        all_rows.extend(selected)
        gold = load_gold(label_dir, inference_records)
        metrics = {**_prf({_key(row) for row in selected}, gold),
                   "fold": index, "inference_records": list(inference_records),
                   "validation_records": list(validation_records),
                   "training_records": train_records,
                   "epochs": training["epochs_completed"]}
        fold_metrics.append(metrics)
        print(f"H32 fold {index + 1}/5 precision={metrics['precision']:.4f} f1={metrics['f1']:.4f}", flush=True)
    gold = load_gold(label_dir, range(1, 101))
    aggregate = {**_prf({_key(row) for row in all_rows}, gold),
                 "predicted": len(all_rows), "offset_errors": offset_errors}
    gates = {
        "precision_at_least_0_78": aggregate["precision"] >= 0.78,
        "f1_at_least_0_55": aggregate["f1"] >= 0.55,
        "recall_at_least_0_40": aggregate["recall"] >= 0.40,
        "every_fold_precision_at_least_0_70": all(row["precision"] >= 0.70 for row in fold_metrics),
        "offset_errors_equal_0": offset_errors == 0,
    }
    agreements = None
    if all(gates.values()):
        agreements = agreement_queue(all_rows, input_dir, label_dir, h20_dir, vietmed_dir)
        (output / "agreement_queue.json").write_text(
            json.dumps(agreements, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "oof_predictions.json").write_text(
        json.dumps(all_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {"folds": fold_metrics, "aggregate": aggregate, "gates": gates,
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
    parser.add_argument("--base", default="models/bami-airace-v15-weighted")
    parser.add_argument("--output", default="experiments/H32_crossfit_high_confidence_voter/results")
    parser.add_argument("--h20", default="turn2/output_v6_expanded_pair")
    parser.add_argument("--vietmed", default="experiments/H_turn2_multimodel_core/proposals_vietmed")
    args = parser.parse_args()
    print(json.dumps(run_experiment(args.input, args.labels, args.base, args.output,
                                    args.h20, args.vietmed), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
