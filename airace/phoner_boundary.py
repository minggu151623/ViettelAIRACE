"""H59: calibrate a PhoNER-COVID19 clinical-mention boundary teacher.

The source taxonomy deliberately combines symptoms and diseases.  This module
therefore evaluates exact character boundaries only and never treats the
source label as a Viettel entity type decision.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

from transformers import AutoModelForTokenClassification

from .schema import Entity
from .train import _device, _load_fast_tokenizer, predict_token_entities, train_model


SOURCE_LABEL = "SYMPTOM_AND_DISEASE"
TRAINING_TYPE = "TRIỆU_CHỨNG"
THRESHOLDS = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85,
              0.90, 0.92, 0.94, 0.96, 0.98)


def _token_offsets(words: list[str]) -> tuple[str, list[tuple[int, int]]]:
    text = " ".join(words)
    offsets: list[tuple[int, int]] = []
    cursor = 0
    for word in words:
        offsets.append((cursor, cursor + len(word)))
        cursor += len(word) + 1
    return text, offsets


def clinical_entities(words: list[str], tags: list[str]) -> tuple[str, list[Entity]]:
    """Convert the combined source BIO label to exact character spans."""
    if len(words) != len(tags):
        raise ValueError("PhoNER word/tag length mismatch")
    text, offsets = _token_offsets(words)
    entities: list[Entity] = []
    start: int | None = None
    end = 0

    def flush() -> None:
        nonlocal start, end
        if start is not None:
            entities.append(
                Entity(text=text[start:end], type=TRAINING_TYPE, position=(start, end))
            )
        start = None
        end = 0

    for (token_start, token_end), tag in zip(offsets, tags):
        prefix, _, label = tag.partition("-")
        if label != SOURCE_LABEL:
            flush()
            continue
        if prefix == "B" or start is None:
            flush()
            start = token_start
        end = token_end
    flush()
    return text, entities


def load_source(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines()):
        if not line.strip():
            continue
        source = json.loads(line)
        text, entities = clinical_entities(source["words"], source["tags"])
        rows.append(
            {
                "record_id": index + 1,
                "text": text,
                "entities": [entity.to_dict() for entity in entities],
            }
        )
    if not rows:
        raise ValueError(f"empty PhoNER source split: {path}")
    return rows


def write_training_jsonl(source: str | Path, target: str | Path) -> dict[str, int]:
    rows = load_source(source)
    output = Path(target)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    return {
        "sentences": len(rows),
        "entities": sum(len(row["entities"]) for row in rows),
    }


def _boundary_set(entities: Iterable[Entity], threshold: float = 0.0) -> set[tuple[int, int]]:
    return {
        entity.position for entity in entities if float(entity.confidence) >= threshold
    }


def boundary_metrics(
    gold_rows: list[dict[str, Any]],
    predictions: list[list[Entity]],
    threshold: float,
) -> dict[str, Any]:
    if len(gold_rows) != len(predictions):
        raise ValueError("gold/prediction length mismatch")
    true_positive = false_positive = false_negative = 0
    for row, predicted in zip(gold_rows, predictions):
        gold = {
            tuple(entity["position"])
            for entity in row["entities"]
        }
        pred = _boundary_set(predicted, threshold)
        true_positive += len(gold & pred)
        false_positive += len(pred - gold)
        false_negative += len(gold - pred)
    precision = true_positive / max(1, true_positive + false_positive)
    recall = true_positive / max(1, true_positive + false_negative)
    f1 = 2 * precision * recall / max(1e-12, precision + recall)
    return {
        "threshold": threshold,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
        "predicted": true_positive + false_positive,
    }


def select_threshold(
    grid: Iterable[dict[str, Any]],
    minimum_precision: float = 0.90,
    minimum_f1: float = 0.65,
) -> dict[str, Any] | None:
    eligible = [
        row for row in grid
        if row["precision"] >= minimum_precision and row["f1"] >= minimum_f1
    ]
    return max(
        eligible,
        key=lambda row: (row["recall"], row["precision"], row["threshold"]),
        default=None,
    )


def predict_split(checkpoint: str | Path, rows: list[dict[str, Any]]) -> list[list[Entity]]:
    tokenizer = _load_fast_tokenizer(checkpoint)
    model = AutoModelForTokenClassification.from_pretrained(str(checkpoint))
    device = _device()
    model.to(device)
    return [
        predict_token_entities(
            row["text"], model=model, tokenizer=tokenizer, device=device,
            max_length=256, stride=64,
        )
        for row in rows
    ]


def calibrate(
    checkpoint: str | Path,
    dev_source: str | Path,
    test_source: str | Path,
) -> dict[str, Any]:
    dev_rows = load_source(dev_source)
    dev_predictions = predict_split(checkpoint, dev_rows)
    grid = [boundary_metrics(dev_rows, dev_predictions, value) for value in THRESHOLDS]
    selected = select_threshold(grid)
    gates = {
        "official_dev_precision_at_least_0.90": selected is not None,
        "official_dev_f1_at_least_0.65": selected is not None,
    }
    report: dict[str, Any] = {
        "threshold_grid": grid,
        "selected": selected,
        "gates": gates,
        "decision": "FAIL",
    }
    if selected is None:
        return report
    test_rows = load_source(test_source)
    test_predictions = predict_split(checkpoint, test_rows)
    test = boundary_metrics(test_rows, test_predictions, selected["threshold"])
    gates.update(
        {
            "official_test_precision_at_least_0.85": test["precision"] >= 0.85,
            "official_test_f1_at_least_0.60": test["f1"] >= 0.60,
        }
    )
    report["test"] = test
    report["decision"] = "PASS" if all(gates.values()) else "FAIL"
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--source-root", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    train = subparsers.add_parser("train")
    train.add_argument("--labels", type=Path, required=True)
    train.add_argument("--validation", type=Path, required=True)
    train.add_argument("--base-model", type=Path, required=True)
    train.add_argument("--checkpoint", type=Path, required=True)
    evaluate = subparsers.add_parser("evaluate")
    evaluate.add_argument("--checkpoint", type=Path, required=True)
    evaluate.add_argument("--source-root", type=Path, required=True)
    evaluate.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()

    if args.command == "prepare":
        results = {}
        for split in ("train", "dev", "test"):
            results[split] = write_training_jsonl(
                args.source_root / f"{split}_syllable.json",
                args.output / f"{split}.jsonl",
            )
        print(json.dumps(results, ensure_ascii=False, indent=2))
    elif args.command == "train":
        report = train_model(
            args.labels,
            args.checkpoint,
            args.base_model,
            epochs=8,
            minimum_epochs=4,
            patience=3,
            learning_rate=3e-5,
            max_length=256,
            stride=64,
            batch_size=16,
            gradient_accumulation=1,
            validation_path=args.validation,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        report = calibrate(
            args.checkpoint,
            args.source_root / "dev_syllable.json",
            args.source_root / "test_syllable.json",
        )
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
