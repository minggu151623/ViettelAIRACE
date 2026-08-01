"""Offline proposal-bank inference for trained BIO checkpoints.

The proposal bank is deliberately separate from competition JSON: it retains
model confidence and source so a later merger can calibrate specialists
without losing evidence at serialization time.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForTokenClassification

from .proposals import Proposal, dump_proposals
from .train import _load_fast_tokenizer, predict_token_entities


def _select_device(value: str) -> torch.device:
    if value == "cpu":
        return torch.device("cpu")
    if value == "cuda":
        if not torch.cuda.is_available():
            raise ValueError("CUDA was requested but is unavailable")
        return torch.device("cuda")
    if value == "mps":
        if not torch.backends.mps.is_available():
            raise ValueError("MPS was requested but is unavailable")
        return torch.device("mps")
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def infer_checkpoint_proposals(
    input_dir: str | Path,
    proposal_dir: str | Path,
    checkpoint: str | Path,
    report_path: str | Path | None = None,
    *,
    source: str = "token_model",
    device: str = "auto",
    max_length: int = 256,
    stride: int = 64,
) -> dict[str, Any]:
    started = time.perf_counter()
    inputs = Path(input_dir)
    target = Path(proposal_dir)
    target.mkdir(parents=True, exist_ok=True)
    records = sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem))
    runtime_device = _select_device(device)
    tokenizer = _load_fast_tokenizer(checkpoint)
    model = AutoModelForTokenClassification.from_pretrained(str(checkpoint))
    model.to(runtime_device)
    completed = 0
    errors: list[dict[str, str]] = []
    counts: dict[str, int] = {}
    for path in records:
        try:
            text = path.read_text(encoding="utf-8")
            entities = predict_token_entities(
                text,
                model=model,
                tokenizer=tokenizer,
                device=runtime_device,
                max_length=max_length,
                stride=stride,
            )
            for entity in entities:
                entity.source = source
            dump_proposals(
                [Proposal.from_entity(entity) for entity in entities],
                target / f"{path.stem}.json",
            )
            for entity in entities:
                counts[entity.type] = counts.get(entity.type, 0) + 1
            completed += 1
        except Exception as exc:
            errors.append({"record": path.stem, "error": str(exc)})
    report = {
        "records": len(records),
        "completed": completed,
        "errors": errors,
        "checkpoint": str(checkpoint),
        "source": source,
        "device": str(runtime_device),
        "max_length": max_length,
        "stride": stride,
        "counts": counts,
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "offline": True,
    }
    if report_path:
        destination = Path(report_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return report
