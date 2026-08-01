from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Iterable

from .schema import Entity, entities_from_json


def _tokens(text: str) -> list[str]:
    return re.findall(r"\w+|[^\w\s]", text.casefold(), flags=re.UNICODE)


def wer(reference: str, hypothesis: str) -> float:
    ref, hyp = _tokens(reference), _tokens(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    previous = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        current = [i]
        for j, h in enumerate(hyp, 1):
            current.append(min(
                current[-1] + 1,
                previous[j] + 1,
                previous[j - 1] + (r != h),
            ))
        previous = current
    return previous[-1] / len(ref)


def jaccard(gold: Iterable[str], pred: Iterable[str]) -> float:
    a, b = set(gold), set(pred)
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _pair(gold: list[Entity], pred: list[Entity]) -> list[tuple[Entity | None, Entity | None]]:
    pairs: list[tuple[Entity | None, Entity | None]] = []
    remaining = set(range(len(pred)))
    for expected in sorted(gold, key=lambda e: e.position):
        same_type = [idx for idx in remaining if pred[idx].type == expected.type]
        if not same_type:
            pairs.append((expected, None))
            continue
        exact = [idx for idx in same_type if pred[idx].position == expected.position]
        idx = min(exact or same_type, key=lambda x: (0 if x in exact else 1, wer(expected.text, pred[x].text), abs(expected.position[0] - pred[x].position[0])))
        remaining.remove(idx)
        pairs.append((expected, pred[idx]))
    pairs.extend((None, pred[idx]) for idx in sorted(remaining, key=lambda i: pred[i].position))
    return pairs


def score_entities(gold: list[Entity], pred: list[Entity]) -> dict[str, float]:
    pairs = _pair(gold, pred)
    if not pairs:
        return {"text_score": 1.0, "assertions_score": 1.0, "candidates_score": 1.0, "final_score": 1.0}
    text_values: list[float] = []
    assertion_values: list[float] = []
    candidate_values: list[float] = []
    candidate_weights: list[float] = []
    for expected, actual in pairs:
        if expected is None or actual is None:
            text_values.append(0.0)
            assertion_values.append(0.0)
            candidate_values.append(0.0)
            candidate_weights.append(float(len((expected.candidates or []) if expected else []) + 1))
            continue
        text_values.append(max(0.0, 1.0 - wer(expected.text, actual.text)))
        assertion_values.append(jaccard(expected.assertions, actual.assertions))
        candidate_values.append(jaccard(expected.candidates or [], actual.candidates or []))
        candidate_weights.append(float(len(expected.candidates or []) + 1))
    text_score = sum(text_values) / len(text_values)
    assertions_score = sum(assertion_values) / len(assertion_values)
    candidates_score = sum(v * w for v, w in zip(candidate_values, candidate_weights)) / sum(candidate_weights)
    return {
        "text_score": text_score,
        "assertions_score": assertions_score,
        "candidates_score": candidates_score,
        "final_score": 0.3 * text_score + 0.3 * assertions_score + 0.4 * candidates_score,
    }


def evaluate_dirs(gold_dir: str | Path, pred_dir: str | Path) -> dict[str, float | int]:
    gold_path, pred_path = Path(gold_dir), Path(pred_dir)
    records = sorted(gold_path.glob("*.json"), key=lambda p: int(p.stem))
    if not records:
        raise ValueError(f"no gold JSON files in {gold_path}")
    scores = [score_entities(
        entities_from_json(json.loads(path.read_text(encoding="utf-8"))),
        entities_from_json(json.loads((pred_path / path.name).read_text(encoding="utf-8"))),
    ) for path in records]
    return {
        "records": len(scores),
        **{name: sum(s[name] for s in scores) / len(scores) for name in ("text_score", "assertions_score", "candidates_score", "final_score")},
    }
