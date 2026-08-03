"""Deterministic masked-language task adaptation on unlabelled Turn2 text."""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForMaskedLM, DataCollatorForLanguageModeling

from .train import _device, _load_fast_tokenizer


class _Windows(Dataset):
    def __init__(self, rows: list[dict[str, list[int]]]) -> None:
        self.rows = rows

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> dict[str, list[int]]:
        return self.rows[index]


def target_windows(
    tokenizer: Any,
    input_dir: str | Path,
    max_length: int = 256,
    stride: int = 32,
) -> list[dict[str, list[int]]]:
    windows: list[dict[str, list[int]]] = []
    for path in sorted(Path(input_dir).glob("*.txt"), key=lambda value: int(value.stem)):
        text = path.read_text(encoding="utf-8")
        encoded = tokenizer(
            text,
            truncation=True,
            max_length=max_length,
            stride=stride,
            return_overflowing_tokens=True,
            padding=False,
        )
        for input_ids, attention_mask in zip(
            encoded["input_ids"], encoded["attention_mask"]
        ):
            windows.append(
                {"input_ids": list(input_ids), "attention_mask": list(attention_mask)}
            )
    if not windows:
        raise ValueError(f"no target text windows found in {input_dir}")
    return windows


def adapt(
    base_model: str | Path,
    input_dir: str | Path,
    output_dir: str | Path,
    *,
    epochs: int = 3,
    batch_size: int = 16,
    learning_rate: float = 5e-5,
    mask_probability: float = 0.15,
    max_length: int = 256,
    stride: int = 32,
    seed: int = 61,
) -> dict[str, Any]:
    started = time.perf_counter()
    random.seed(seed)
    torch.manual_seed(seed)
    tokenizer = _load_fast_tokenizer(base_model)
    model, loading = AutoModelForMaskedLM.from_pretrained(
        str(base_model), output_loading_info=True,
    )
    windows = target_windows(tokenizer, input_dir, max_length=max_length, stride=stride)
    collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer, mlm=True, mlm_probability=mask_probability,
    )
    loader = DataLoader(
        _Windows(windows), batch_size=batch_size, shuffle=True,
        generator=torch.Generator().manual_seed(seed), collate_fn=collator,
    )
    device = _device()
    model.to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=learning_rate)
    total_steps = max(1, len(loader) * epochs)
    warmup = max(1, round(total_steps * 0.1))

    def scale(step: int) -> float:
        if step < warmup:
            return (step + 1) / warmup
        return max(0.0, (total_steps - step) / max(1, total_steps - warmup))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, scale)
    history: list[dict[str, float]] = []
    for epoch in range(1, epochs + 1):
        model.train()
        losses: list[float] = []
        for batch in loader:
            batch = {key: value.to(device) for key, value in batch.items()}
            optimizer.zero_grad(set_to_none=True)
            result = model(**batch)
            result.loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            losses.append(float(result.loss.detach().cpu()))
        mean_loss = sum(losses) / max(1, len(losses))
        history.append(
            {
                "epoch": epoch,
                "mean_loss": round(mean_loss, 6),
                "perplexity": round(math.exp(min(20.0, mean_loss)), 6),
            }
        )

    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(target)
    tokenizer.save_pretrained(target)
    report = {
        "method": "Turn2_task_adaptive_masked_language_pretraining",
        "input_records": len(list(Path(input_dir).glob("*.txt"))),
        "windows": len(windows),
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "mask_probability": mask_probability,
        "max_length": max_length,
        "stride": stride,
        "seed": seed,
        "device": str(device),
        "missing_keys_at_load": sorted(loading.get("missing_keys", [])),
        "unexpected_keys_at_load": sorted(loading.get("unexpected_keys", [])),
        "history": history,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    (target / "tapt_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-model", type=Path, required=True)
    parser.add_argument("--input", type=Path, default=Path("turn2/input"))
    parser.add_argument("--output", type=Path, default=Path("models/h61-turn2-tapt-base"))
    args = parser.parse_args()
    print(json.dumps(adapt(args.base_model, args.input, args.output),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
