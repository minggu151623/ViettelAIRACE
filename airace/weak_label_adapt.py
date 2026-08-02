"""Record-held-out token-model adaptation on frozen H23 weak labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import torch
from transformers import AutoModelForTokenClassification

from .proposal_pu import DEFAULT_DEV, DEFAULT_TEST, DEFAULT_TRAIN, TYPE_ORDER, _prf
from .train import _load_fast_tokenizer, predict_token_entities, train_model


def export_jsonl(input_dir: str | Path, label_dir: str | Path,
                 records: Iterable[int], output_path: str | Path) -> int:
    inputs, labels = Path(input_dir), Path(label_dir)
    rows = []
    for record in sorted(records):
        rows.append({
            "record_id": record,
            "text": (inputs / f"{record}.txt").read_text(encoding="utf-8"),
            "entities": json.loads((labels / f"{record}.json").read_text(encoding="utf-8")),
        })
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
                      encoding="utf-8")
    return len(rows)


def _key(entity: Any) -> tuple[int, int, str]:
    return (int(entity.position[0]), int(entity.position[1]), str(entity.type))


def evaluate_checkpoint(checkpoint: str | Path, input_dir: str | Path,
                        label_dir: str | Path, records: Iterable[int]) -> dict[str, Any]:
    device = torch.device("mps" if torch.backends.mps.is_available() else
                          "cuda" if torch.cuda.is_available() else "cpu")
    tokenizer = _load_fast_tokenizer(checkpoint)
    model = AutoModelForTokenClassification.from_pretrained(str(checkpoint)).to(device)
    predicted: set[tuple[int, int, str, int]] = set()
    gold: set[tuple[int, int, str, int]] = set()
    offset_errors = 0
    per_record: dict[int, list[tuple[int, int, str]]] = {}
    for record in sorted(records):
        raw = (Path(input_dir) / f"{record}.txt").read_text(encoding="utf-8")
        entities = predict_token_entities(raw, model=model, tokenizer=tokenizer,
                                          device=device, max_length=256, stride=64)
        keys = sorted(_key(entity) for entity in entities)
        per_record[record] = keys
        for entity in entities:
            start, end = entity.position
            offset_errors += int(raw[start:end] != entity.text)
            predicted.add((start, end, entity.type, record))
        for value in json.loads((Path(label_dir) / f"{record}.json").read_text(encoding="utf-8")):
            start, end = value["position"]
            gold.add((int(start), int(end), str(value["type"]), record))
    per_type: dict[str, Any] = {}
    for kind in TYPE_ORDER:
        p = {row for row in predicted if row[2] == kind}
        g = {row for row in gold if row[2] == kind}
        per_type[kind] = {**_prf(p, g), "gold_support": len(g)}
    return {**_prf(predicted, gold), "offset_errors": offset_errors,
            "per_type": per_type, "per_record": per_record}


def dev_gates(result: dict[str, Any]) -> dict[str, bool]:
    return {
        "dev_f1_at_least_0_82": result["f1"] >= 0.82,
        "dev_precision_at_least_0_82": result["precision"] >= 0.82,
        "dev_offset_errors_equal_0": result["offset_errors"] == 0,
    }


def final_test_gates(first: dict[str, Any], second: dict[str, Any]) -> dict[str, bool]:
    supported = [value for value in first["per_type"].values()
                 if value["gold_support"] >= 20]
    return {
        "test_f1_at_least_0_78": first["f1"] >= 0.78,
        "test_precision_at_least_0_78": first["precision"] >= 0.78,
        "supported_type_f1_at_least_0_60": all(value["f1"] >= 0.60 for value in supported),
        "deterministic_inference": first["per_record"] == second["per_record"],
    }


def run_experiment(input_dir: str | Path, label_dir: str | Path,
                   base_model: str | Path, output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    data = output / "data"
    checkpoint = Path("models/h30-bami-weak-label")
    export_jsonl(input_dir, label_dir, DEFAULT_TRAIN, data / "train.jsonl")
    export_jsonl(input_dir, label_dir, DEFAULT_DEV, data / "dev.jsonl")
    export_jsonl(input_dir, label_dir, DEFAULT_TEST, data / "test.jsonl")
    training = train_model(
        data / "train.jsonl", checkpoint, base_model,
        epochs=8, max_length=256, learning_rate=2e-5, stride=64,
        batch_size=4, gradient_accumulation=4, seed=4331, patience=2,
        validation_path=data / "dev.jsonl", class_weighting=True,
    )
    dev = evaluate_checkpoint(checkpoint, input_dir, label_dir, DEFAULT_DEV)
    gates = dev_gates(dev)
    report: dict[str, Any] = {"training": training, "dev": dev,
                             "dev_gates": gates, "test": None,
                             "test_gates": None, "status": "dev_failed_test_canceled"}
    if all(gates.values()):
        test_first = evaluate_checkpoint(checkpoint, input_dir, label_dir, DEFAULT_TEST)
        test_second = evaluate_checkpoint(checkpoint, input_dir, label_dir, DEFAULT_TEST)
        final = final_test_gates(test_first, test_second)
        report.update({"test": test_first, "test_gates": final,
                       "status": "passed" if all(final.values()) else "test_failed"})
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="turn2/input")
    parser.add_argument("--labels", default="turn2/output_v8_candidate_semantic")
    parser.add_argument("--base", default="models/bami-airace-v15-weighted")
    parser.add_argument("--output", default="experiments/H30_weak_label_bami_adaptation/results")
    args = parser.parse_args()
    report = run_experiment(args.input, args.labels, args.base, args.output)
    print(json.dumps({key: report[key] for key in ("status", "dev", "dev_gates", "test", "test_gates")},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
