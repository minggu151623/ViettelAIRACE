from __future__ import annotations

import json
import math
import random
import re
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from transformers import (
    AutoModelForTokenClassification,
    AutoTokenizer,
    PreTrainedTokenizerFast,
)

from .schema import ENTITY_TYPES, Entity, entities_from_json


TYPE_ORDER = sorted(ENTITY_TYPES)
BIO_LABELS = ["O"] + [
    f"{prefix}-{kind}" for kind in TYPE_ORDER for prefix in ("B", "I")
]
LABEL_TO_ID = {label: index for index, label in enumerate(BIO_LABELS)}


def _device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def _load_fast_tokenizer(checkpoint: str | Path) -> Any:
    try:
        return AutoTokenizer.from_pretrained(str(checkpoint), use_fast=True)
    except ValueError as exc:
        if "TokenizersBackend" not in str(exc):
            raise
        return PreTrainedTokenizerFast.from_pretrained(
            str(checkpoint),
            tokenizer_file=str(Path(checkpoint) / "tokenizer.json"),
            bos_token="<s>",
            eos_token="</s>",
            cls_token="<s>",
            sep_token="</s>",
            pad_token="<pad>",
            unk_token="<unk>",
            mask_token="<mask>",
        )


def _load_rows(path: str | Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not rows:
        raise ValueError("labels file is empty")
    for row in rows:
        text = str(row.get("text", ""))
        entities = entities_from_json(row.get("entities", []))
        for entity in entities:
            start, end = entity.position
            if not (0 <= start < end <= len(text)):
                raise ValueError(
                    f"invalid offset in record {row.get('record_id')}: {entity.position}"
                )
            if text[start:end] != entity.text:
                raise ValueError(
                    f"offset/text mismatch in record {row.get('record_id')}: "
                    f"{entity.text!r} != {text[start:end]!r}"
                )
        row["_entities"] = entities
    return rows


def _split_rows(
    rows: list[dict[str, Any]], validation_ratio: float, seed: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if len(rows) < 3 or validation_ratio <= 0:
        return rows, []
    ordered = list(rows)
    random.Random(seed).shuffle(ordered)
    valid_count = max(1, round(len(ordered) * validation_ratio))
    return ordered[valid_count:], ordered[:valid_count]


def _entity_for_token(
    start: int, end: int, entities: list[Entity]
) -> Entity | None:
    matches = [
        entity
        for entity in entities
        if start < entity.position[1] and end > entity.position[0]
    ]
    if not matches:
        return None
    # Clean annotation files should not overlap. Prefer the smallest mention if
    # a draft still contains a nested span, because it produces tighter BIO
    # boundaries and avoids teaching the model an entire prose clause.
    return min(matches, key=lambda entity: entity.position[1] - entity.position[0])


def _tokenize_rows(
    tokenizer: Any,
    rows: Iterable[dict[str, Any]],
    max_length: int,
    stride: int,
) -> list[dict[str, torch.Tensor]]:
    features: list[dict[str, torch.Tensor]] = []
    for row_index, row in enumerate(rows):
        text = row["text"]
        entities: list[Entity] = row["_entities"]
        encoded = tokenizer(
            text,
            truncation=True,
            max_length=max_length,
            stride=stride,
            return_overflowing_tokens=True,
            return_offsets_mapping=True,
            padding="max_length",
        )
        for feature_index in range(len(encoded["input_ids"])):
            offsets = encoded["offset_mapping"][feature_index]
            labels: list[int] = []
            previous_entity: Entity | None = None
            for start, end in offsets:
                if start == end:
                    labels.append(-100)
                    previous_entity = None
                    continue
                entity = _entity_for_token(start, end, entities)
                if entity is None:
                    labels.append(LABEL_TO_ID["O"])
                    previous_entity = None
                    continue
                prefix = "I" if previous_entity is entity else "B"
                labels.append(LABEL_TO_ID[f"{prefix}-{entity.type}"])
                previous_entity = entity
            features.append(
                {
                    "input_ids": torch.tensor(
                        encoded["input_ids"][feature_index], dtype=torch.long
                    ),
                    "attention_mask": torch.tensor(
                        encoded["attention_mask"][feature_index], dtype=torch.long
                    ),
                    "labels": torch.tensor(labels, dtype=torch.long),
                    "row_index": torch.tensor(row_index, dtype=torch.long),
                }
            )
    return features


class _FeatureDataset(Dataset):
    def __init__(self, values: list[dict[str, torch.Tensor]]) -> None:
        self.values = values

    def __len__(self) -> int:
        return len(self.values)

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]:
        return self.values[index]


def _strict_span_set(text: str, entities: Iterable[Entity]) -> set[tuple[int, int, str]]:
    return {
        (entity.position[0], entity.position[1], entity.type)
        for entity in entities
        if text[entity.position[0] : entity.position[1]] == entity.text
    }


def _prf(
    gold_sets: Iterable[set[tuple[int, int, str]]],
    pred_sets: Iterable[set[tuple[int, int, str]]],
) -> dict[str, float]:
    true_positive = false_positive = false_negative = 0
    for gold, pred in zip(gold_sets, pred_sets):
        true_positive += len(gold & pred)
        false_positive += len(pred - gold)
        false_negative += len(gold - pred)
    precision = true_positive / max(1, true_positive + false_positive)
    recall = true_positive / max(1, true_positive + false_negative)
    f1 = 2 * precision * recall / max(1e-12, precision + recall)
    return {
        "precision": round(precision, 6),
        "recall": round(recall, 6),
        "f1": round(f1, 6),
        "true_positive": true_positive,
        "false_positive": false_positive,
        "false_negative": false_negative,
    }


@dataclass
class _EarlyStop:
    best: float = -1.0
    stale_epochs: int = 0


def train_model(
    labels_path: str | Path,
    output_dir: str | Path,
    base_model: str | Path,
    epochs: int = 5,
    max_length: int = 256,
    learning_rate: float = 3e-5,
    stride: int = 64,
    validation_ratio: float = 0.2,
    batch_size: int = 4,
    gradient_accumulation: int = 4,
    seed: int = 42,
    patience: int = 2,
    minimum_epochs: int = 0,
    validation_path: str | Path | None = None,
    class_weighting: bool = False,
) -> dict[str, Any]:
    """Fine-tune a real sliding-window token classifier.

    This replaces the V1 demonstrator which silently truncated every document
    after its first 224 tokens and evaluated no held-out records.
    """

    started = time.perf_counter()
    torch.manual_seed(seed)
    random.seed(seed)
    rows = _load_rows(labels_path)
    if validation_path and Path(validation_path).exists():
        train_rows = rows
        valid_rows = _load_rows(validation_path)
        validation_source = str(validation_path)
    else:
        train_rows, valid_rows = _split_rows(rows, validation_ratio, seed)
        validation_source = "deterministic_split"
    tokenizer = _load_fast_tokenizer(base_model)
    if not tokenizer.is_fast:
        raise ValueError(
            "The V2 trainer requires a fast tokenizer so offsets remain exact. "
            "Use BamiBERT/XLM-R, or provide a fast-tokenizer checkpoint."
        )
    id2label = {index: label for index, label in enumerate(BIO_LABELS)}
    label2id = {label: index for index, label in id2label.items()}
    model = AutoModelForTokenClassification.from_pretrained(
        str(base_model),
        num_labels=len(BIO_LABELS),
        id2label=id2label,
        label2id=label2id,
        ignore_mismatched_sizes=True,
    )
    train_features = _tokenize_rows(
        tokenizer, train_rows, max_length=max_length, stride=stride
    )
    class_weights: torch.Tensor | None = None
    if class_weighting:
        counts = torch.zeros(len(BIO_LABELS), dtype=torch.float)
        for feature in train_features:
            labels = feature["labels"]
            valid = labels[labels >= 0]
            counts += torch.bincount(valid, minlength=len(BIO_LABELS)).float()
        nonzero = counts[counts > 0]
        reference = float(nonzero.median()) if len(nonzero) else 1.0
        weights = torch.sqrt(reference / counts.clamp_min(1.0))
        weights = weights.clamp(0.25, 8.0)
        weights[LABEL_TO_ID["O"]] = min(float(weights[LABEL_TO_ID["O"]]), 0.25)
        class_weights = weights
    train_loader = DataLoader(
        _FeatureDataset(train_features),
        batch_size=batch_size,
        shuffle=True,
        generator=torch.Generator().manual_seed(seed),
    )
    device = _device()
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    total_optimizer_steps = max(
        1, math.ceil(len(train_loader) / gradient_accumulation) * epochs
    )
    warmup_steps = max(1, round(total_optimizer_steps * 0.1))

    def learning_rate_scale(step: int) -> float:
        if step < warmup_steps:
            return (step + 1) / warmup_steps
        return max(
            0.0,
            (total_optimizer_steps - step)
            / max(1, total_optimizer_steps - warmup_steps),
        )

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, learning_rate_scale)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    losses: list[float] = []
    history: list[dict[str, Any]] = []
    early = _EarlyStop()

    for epoch in range(1, epochs + 1):
        model.train()
        optimizer.zero_grad(set_to_none=True)
        epoch_losses: list[float] = []
        for batch_index, batch in enumerate(train_loader, 1):
            values = {
                key: value.to(device)
                for key, value in batch.items()
                if key in {"input_ids", "attention_mask", "labels"}
            }
            result = model(**values)
            raw_loss = (
                F.cross_entropy(
                    result.logits.view(-1, len(BIO_LABELS)),
                    values["labels"].view(-1),
                    weight=class_weights.to(device) if class_weights is not None else None,
                    ignore_index=-100,
                )
                if class_weights is not None
                else result.loss
            )
            loss = raw_loss / gradient_accumulation
            loss.backward()
            epoch_losses.append(float(raw_loss.detach().cpu()))
            if (
                batch_index % gradient_accumulation == 0
                or batch_index == len(train_loader)
            ):
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                optimizer.step()
                scheduler.step()
                optimizer.zero_grad(set_to_none=True)
        losses.extend(epoch_losses)

        metrics: dict[str, Any] = {
            "epoch": epoch,
            "loss": round(sum(epoch_losses) / max(1, len(epoch_losses)), 6),
        }
        if valid_rows:
            predictions = [
                predict_token_entities(
                    row["text"],
                    model=model,
                    tokenizer=tokenizer,
                    device=device,
                    max_length=max_length,
                    stride=stride,
                )
                for row in valid_rows
            ]
            metrics.update(
                _prf(
                    [
                        _strict_span_set(row["text"], row["_entities"])
                        for row in valid_rows
                    ],
                    [
                        _strict_span_set(row["text"], entities)
                        for row, entities in zip(valid_rows, predictions)
                    ],
                )
            )
            monitored = float(metrics["f1"])
        else:
            monitored = -float(metrics["loss"])
        history.append(metrics)

        if monitored > early.best:
            early.best = monitored
            early.stale_epochs = 0
            model.save_pretrained(target)
            tokenizer.save_pretrained(target)
        else:
            early.stale_epochs += 1
            if early.stale_epochs >= patience and epoch >= minimum_epochs:
                break

    type_counts = Counter(
        entity.type for row in rows for entity in row["_entities"]
    )
    report = {
        "examples": len(rows),
        "train_examples": len(train_rows),
        "validation_examples": len(valid_rows),
        "validation_source": validation_source,
        "windows": len(train_features),
        "epochs_requested": epochs,
        "epochs_completed": len(history),
        "minimum_epochs": minimum_epochs,
        "device": str(device),
        "mean_loss": round(sum(losses) / max(1, len(losses)), 6),
        "best_validation_f1": round(max((h.get("f1", 0.0) for h in history), default=0.0), 6),
        "entity_counts": dict(type_counts),
        "max_length": max_length,
        "stride": stride,
        "output_dir": str(target),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "class_weighting": class_weighting,
        "class_weights": (
            {
                BIO_LABELS[index]: round(float(value), 6)
                for index, value in enumerate(class_weights)
            }
            if class_weights is not None
            else None
        ),
        "history": history,
    }
    (target / "training_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def _trim_span(text: str, start: int, end: int) -> tuple[int, int]:
    # Sliding-window boundaries may expose partial token offsets such as
    # "G" / "ãy". An entity boundary cannot validly split an alphanumeric
    # word, so restore the complete word in the immutable raw text.
    while (
        start > 0
        and start < len(text)
        and text[start].isalnum()
        and text[start - 1].isalnum()
    ):
        start -= 1
    while (
        end < len(text)
        and end > 0
        and text[end - 1].isalnum()
        and text[end].isalnum()
    ):
        end += 1
    while start < end and (text[start].isspace() or text[start] in ",;:.!?()[]"):
        start += 1
    while end > start and (text[end - 1].isspace() or text[end - 1] in ",;:.!?()[]"):
        end -= 1
    return start, end


def _decode_token_predictions(
    text: str,
    token_values: list[tuple[int, int, str, float]],
) -> list[Entity]:
    entities: list[Entity] = []
    current_type: str | None = None
    current_start = current_end = 0
    current_scores: list[float] = []

    def flush() -> None:
        nonlocal current_type, current_start, current_end, current_scores
        if current_type is None:
            return
        start, end = _trim_span(text, current_start, current_end)
        if start < end:
            entities.append(
                Entity(
                    text=text[start:end],
                    type=current_type,
                    position=(start, end),
                    candidates=[] if current_type in {"CHẨN_ĐOÁN", "THUỐC"} else None,
                    confidence=sum(current_scores) / max(1, len(current_scores)),
                    source="token_model",
                )
            )
        current_type = None
        current_scores = []

    for start, end, label, confidence in token_values:
        if label == "O" or "-" not in label:
            flush()
            continue
        prefix, kind = label.split("-", 1)
        gap = text[current_end:start] if current_type is not None else ""
        continues = (
            prefix == "I"
            and current_type == kind
            and not re.search(r"[\n.!?;]", gap)
        )
        if not continues:
            flush()
            current_type = kind
            current_start = start
            current_end = end
            current_scores = [confidence]
        else:
            current_end = max(current_end, end)
            current_scores.append(confidence)
    flush()
    return entities


def predict_token_entities(
    text: str,
    checkpoint: str | Path | None = None,
    *,
    model: Any | None = None,
    tokenizer: Any | None = None,
    device: torch.device | None = None,
    max_length: int = 256,
    stride: int = 64,
) -> list[Entity]:
    """Predict exact character spans over every sliding window in a document."""

    if model is None or tokenizer is None:
        if checkpoint is None:
            raise ValueError("checkpoint is required when model/tokenizer are not supplied")
        tokenizer = _load_fast_tokenizer(checkpoint)
        model = AutoModelForTokenClassification.from_pretrained(str(checkpoint))
        device = device or _device()
        model.to(device)
    device = device or next(model.parameters()).device
    model.eval()
    encoded = tokenizer(
        text,
        truncation=True,
        max_length=max_length,
        stride=stride,
        return_overflowing_tokens=True,
        return_offsets_mapping=True,
        padding="max_length",
        return_tensors="pt",
    )
    # Average duplicate token probabilities in overlap regions.
    accumulated: dict[tuple[int, int], list[torch.Tensor]] = {}
    batch_size = 8
    with torch.no_grad():
        for batch_start in range(0, encoded["input_ids"].shape[0], batch_size):
            batch_end = batch_start + batch_size
            result = model(
                input_ids=encoded["input_ids"][batch_start:batch_end].to(device),
                attention_mask=encoded["attention_mask"][batch_start:batch_end].to(device),
            )
            probabilities = torch.softmax(result.logits, dim=-1).cpu()
            for local_index in range(probabilities.shape[0]):
                feature_index = batch_start + local_index
                for token_index, (start, end) in enumerate(
                    encoded["offset_mapping"][feature_index].tolist()
                ):
                    if start == end:
                        continue
                    accumulated.setdefault((start, end), []).append(
                        probabilities[local_index, token_index]
                    )

    id2label = {
        int(index): label for index, label in model.config.id2label.items()
    }
    token_values: list[tuple[int, int, str, float]] = []
    for (start, end), values in sorted(accumulated.items()):
        mean = torch.stack(values).mean(dim=0)
        label_id = int(mean.argmax())
        token_values.append(
            (start, end, id2label[label_id], float(mean[label_id]))
        )
    return _decode_token_predictions(text, token_values)
