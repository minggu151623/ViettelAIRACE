from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

from .assertions import attach_assertions
from .candidates import CandidateResolver
from .detector import detect_entities
from .resources import load_lexicon
from .schema import Entity
from .validator import validate_entities
from .normalize import normalize_key


def _has_token_checkpoint(checkpoint: str | Path | None) -> bool:
    if not checkpoint:
        return False
    path = Path(checkpoint)
    # Current Hugging Face save_pretrained checkpoints use model.safetensors
    # (or pytorch_model.bin). The legacy demonstrator used heads.pt. Requiring
    # only heads.pt silently disabled every real model trained by train.py.
    return (path / "config.json").exists() and any(
        (path / filename).exists()
        for filename in ("model.safetensors", "pytorch_model.bin", "heads.pt")
    )


def _infer_with_checkpoint(text: str, checkpoint: str | Path) -> list[Entity]:
    from .train import predict_token_entities

    predicted = predict_token_entities(text, checkpoint=checkpoint)
    return _merge_checkpoint_rules(text, predicted)


def _merge_checkpoint_rules(text: str, predicted: list[Entity]) -> list[Entity]:
    # The learned model is responsible for ambiguous spans and types. Exact
    # medication/lab grammar remains a useful high-precision safety net.
    rule_entities = detect_entities(text, load_lexicon(), profile="baseline")
    for rule in rule_entities:
        if rule.type not in {
            "THUỐC",
            "TÊN_XÉT_NGHIỆM",
            "KẾT_QUẢ_XÉT_NGHIỆM",
        }:
            continue
        if any(
            entity.position[0] < rule.position[1]
            and rule.position[0] < entity.position[1]
            for entity in predicted
        ):
            continue
        predicted.append(rule)
    predicted.sort(key=lambda entity: entity.position)
    return predicted


def infer_text(
    text: str,
    resolver: CandidateResolver | None = None,
    model_checkpoint: str | Path | None = None,
    profile: str = "precision",
) -> list[Entity]:
    entities = (
        _infer_with_checkpoint(text, model_checkpoint)
        if _has_token_checkpoint(model_checkpoint)
        else detect_entities(text, load_lexicon(), profile=profile)
    )
    # Assertions are deliberately recomputed from the raw section and local
    # scope. The token model only decides span/type, the current bottleneck.
    attach_assertions(entities, text)
    resolver = resolver or CandidateResolver(
        use_catalog=profile not in {"baseline", "section_only"},
        strict_strength=profile == "baseline_strength",
    )
    for entity in entities:
        original_candidates = list(entity.candidates or []) if entity.type in {"CHẨN_ĐOÁN", "THUỐC"} else None
        resolver.resolve(entity, text)
        if (
            profile == "baseline_strength"
            and entity.type == "THUỐC"
            and not original_candidates
            and not re.search(r"\b\d+(?:[.,]\d+)?\s*(?:mg|g|mcg|µg|ml|unit)", entity.text, re.IGNORECASE)
            and not any(
                "|" not in raw_key
                and normalize_key(raw_key) in normalize_key(entity.text)
                for raw_key in resolver.lexicon.get("drug_codes", {})
            )
        ):
            entity.candidates = []
    entities.sort(key=lambda e: e.position)
    validate_entities(entities, text)
    return entities


def infer_directory(
    input_dir: str | Path,
    output_dir: str | Path,
    report_path: str | Path | None = None,
    model_checkpoint: str | Path | None = None,
    profile: str = "precision",
) -> dict[str, Any]:
    started = time.perf_counter()
    input_path, output_path = Path(input_dir), Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    resolver = CandidateResolver(
        use_catalog=profile not in {"baseline", "section_only"},
        strict_strength=profile == "baseline_strength",
    )
    counts: Counter[str] = Counter()
    candidate_count = 0
    assertion_count = 0
    errors: list[dict[str, str]] = []
    token_bundle: tuple[Any, Any, Any] | None = None
    if _has_token_checkpoint(model_checkpoint):
        from transformers import AutoModelForTokenClassification
        from .train import _device, _load_fast_tokenizer

        tokenizer = _load_fast_tokenizer(model_checkpoint)
        model = AutoModelForTokenClassification.from_pretrained(str(model_checkpoint))
        device = _device()
        model.to(device)
        model.eval()
        token_bundle = (model, tokenizer, device)
    records = sorted(input_path.glob("*.txt"), key=lambda p: int(p.stem))
    for path in records:
        try:
            text = path.read_text(encoding="utf-8")
            if token_bundle is None:
                entities = infer_text(text, resolver, model_checkpoint, profile)
            else:
                from .train import predict_token_entities

                model, tokenizer, device = token_bundle
                entities = _merge_checkpoint_rules(
                    text,
                    predict_token_entities(
                        text,
                        model=model,
                        tokenizer=tokenizer,
                        device=device,
                    ),
                )
                attach_assertions(entities, text)
                for entity in entities:
                    resolver.resolve(entity, text)
                entities.sort(key=lambda entity: entity.position)
                validate_entities(entities, text)
            for entity in entities:
                counts[entity.type] += 1
                assertion_count += len(entity.assertions)
                if entity.type in {"CHẨN_ĐOÁN", "THUỐC"} and entity.candidates:
                    candidate_count += 1
            (output_path / f"{path.stem}.json").write_text(
                json.dumps([e.to_dict() for e in entities], ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            errors.append({"record": path.stem, "error": str(exc)})
            (output_path / f"{path.stem}.json").write_text("[]\n", encoding="utf-8")
    report = {
        "records": len(records),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "entity_counts": dict(counts),
        "entities_with_candidates": candidate_count,
        "assertion_count": assertion_count,
        "errors": errors,
        "offline": True,
        "model": "token-model+rules" if _has_token_checkpoint(model_checkpoint) else "rules+dictionary",
        "profile": profile,
    }
    if report_path:
        Path(report_path).parent.mkdir(parents=True, exist_ok=True)
        Path(report_path).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
