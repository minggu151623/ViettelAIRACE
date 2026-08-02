"""Record-held-out positive-unlabeled proposal and assertion experiments.

H23 is an externally useful pseudo target, not organizer ground truth.  A span
missing from H23 therefore remains unlabeled.  This module uses bagged linear
models and reports transfer from the frozen H20 baseline to H23-like additions;
it never packages a competition artifact.
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .assertions import infer_assertions
from .ontology_qwen import cached_ollama_embeddings
from .proposals import Proposal, load_proposals
from .schema import ASSERTIONS, ENTITY_TYPES, Entity


SOURCES = ("vietmed_ner", "bami_v15", "bami_v3")
ASSERTION_ORDER = ("isHistorical", "isNegated", "isFamily")
TYPE_ORDER = tuple(sorted(ENTITY_TYPES))
DEFAULT_TRAIN = (2, 4, 5, 8, 9, 10, 11, 12, 13, 16, 17, 18, 19, 21, 22, 23, 24, 25, 27, 28, 30, 31, 34, 35, 36, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 51, 52, 53, 55, 58, 60, 61, 63, 64, 65, 66, 67, 71, 73, 74, 76, 77, 79, 80, 81, 82, 83, 86, 87, 88, 90, 91, 92, 93, 94, 95, 96, 97, 98, 100)
DEFAULT_DEV = (3, 6, 20, 26, 32, 38, 39, 50, 56, 62, 69, 70, 72, 75, 78)
DEFAULT_TEST = (1, 7, 14, 15, 29, 33, 37, 54, 57, 59, 68, 84, 85, 89, 99)


def _source_family(value: str) -> str:
    lowered = value.casefold()
    if "vietmed" in lowered:
        return "vietmed_ner"
    if "v15" in lowered:
        return "bami_v15"
    if "v3" in lowered:
        return "bami_v3"
    return lowered


def _entity_key(value: dict[str, Any] | Entity | "PURow") -> tuple[int, int, str]:
    if isinstance(value, dict):
        return int(value["position"][0]), int(value["position"][1]), str(value["type"])
    return int(value.position[0]), int(value.position[1]), str(value.type)


def _load_json_entities(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


@dataclass
class PURow:
    record: int
    text: str
    type: str
    position: tuple[int, int]
    confidences: dict[str, float]
    assertions: dict[str, tuple[str, ...]]
    context: str
    section: str
    positive: bool = False
    overlaps_h20: bool = False

    @property
    def source_count(self) -> int:
        return len(self.confidences)

    @property
    def key(self) -> tuple[int, int, str]:
        return self.position[0], self.position[1], self.type


def _section(raw: str, start: int) -> str:
    before = raw[:start]
    matches = list(re.finditer(r"(?:^|\n)\s*(?:\d+\.)?\s*([^\n:]{2,80})(?::|\n)", before))
    return matches[-1].group(1).strip().casefold() if matches else ""


def _marked_context(raw: str, start: int, end: int, kind: str) -> str:
    left = raw[max(0, start - 180):start]
    right = raw[end:min(len(raw), end + 180)]
    return f"Loại đề xuất: {kind}. Ngữ cảnh: {left} ⟦{raw[start:end]}⟧ {right}"


def collect_rows(
    input_dir: str | Path,
    h23_dir: str | Path,
    h20_dir: str | Path,
    proposal_dirs: Sequence[str | Path],
) -> tuple[list[PURow], dict[int, set[tuple[int, int, str]]], dict[int, set[tuple[int, int, str]]]]:
    inputs, h23, h20 = Path(input_dir), Path(h23_dir), Path(h20_dir)
    banks = [Path(value) for value in proposal_dirs]
    rows: list[PURow] = []
    h23_keys: dict[int, set[tuple[int, int, str]]] = {}
    h20_keys: dict[int, set[tuple[int, int, str]]] = {}
    for record in range(1, 101):
        raw = (inputs / f"{record}.txt").read_text(encoding="utf-8")
        h23_values = _load_json_entities(h23 / f"{record}.json")
        h20_values = _load_json_entities(h20 / f"{record}.json")
        h23_keys[record] = {_entity_key(value) for value in h23_values}
        h20_keys[record] = {_entity_key(value) for value in h20_values}
        h20_intervals = [tuple(value["position"]) for value in h20_values]
        grouped: dict[tuple[int, int, str, str], list[Proposal]] = defaultdict(list)
        for bank in banks:
            for proposal in load_proposals(bank / f"{record}.json"):
                grouped[(*proposal.position, proposal.type, proposal.text)].append(proposal)
        for (start, end, kind, text), values in grouped.items():
            if (
                kind not in ENTITY_TYPES
                or not (0 <= start < end <= len(raw))
                or raw[start:end] != text
                or "\n" in text
                or "\r" in text
                or not any(character.isalpha() for character in text)
            ):
                continue
            confidences: dict[str, float] = {}
            assertion_votes: dict[str, tuple[str, ...]] = {}
            for proposal in values:
                source = _source_family(proposal.source)
                if source not in SOURCES:
                    continue
                if proposal.confidence >= confidences.get(source, -math.inf):
                    confidences[source] = float(proposal.confidence)
                    assertion_votes[source] = tuple(proposal.assertions)
            if not confidences:
                continue
            rows.append(
                PURow(
                    record=record,
                    text=text,
                    type=kind,
                    position=(start, end),
                    confidences=confidences,
                    assertions=assertion_votes,
                    context=_marked_context(raw, start, end, kind),
                    section=_section(raw, start),
                    positive=(start, end, kind) in h23_keys[record],
                    overlaps_h20=any(max(start, left) < min(end, right) for left, right in h20_intervals),
                )
            )
    rows.sort(key=lambda row: (row.record, row.position, row.type, row.text))
    return rows, h23_keys, h20_keys


def structured_features(rows: Sequence[PURow]) -> np.ndarray:
    matrix: list[list[float]] = []
    section_cues = ("tiền sử", "chẩn đoán", "triệu chứng", "xét nghiệm", "thuốc", "điều trị")
    for row in rows:
        confidences = [row.confidences.get(source, 0.0) for source in SOURCES]
        present = [float(source in row.confidences) for source in SOURCES]
        values = list(row.confidences.values())
        letters = [character for character in row.text if character.isalpha()]
        features = present + confidences
        features += [
            float(row.source_count),
            float(np.mean(values)),
            float(np.max(values)),
            float(np.min(values)),
            float(np.std(values)),
            math.log1p(len(row.text)),
            math.log1p(len(row.text.split())),
            sum(character.isdigit() for character in row.text) / max(1, len(row.text)),
            sum(character.isupper() for character in letters) / max(1, len(letters)),
            sum(not character.isalnum() and not character.isspace() for character in row.text) / max(1, len(row.text)),
            float(bool(re.search(r"\b\d+(?:[.,]\d+)?\s*(?:mg|mcg|g|ml|mmol|%|mmhg)\b", row.text, re.I))),
        ]
        features += [float(row.type == kind) for kind in TYPE_ORDER]
        features += [float(cue in row.section) for cue in section_cues]
        matrix.append(features)
    return np.asarray(matrix, dtype=np.float32)


def _fit_pu_bags(
    x_train: np.ndarray,
    train_rows: Sequence[PURow],
    x_all: np.ndarray,
    all_rows: Sequence[PURow],
    *,
    seeds: int = 31,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    predictions = np.zeros((seeds, len(x_all)), dtype=np.float32)
    diagnostics: dict[str, Any] = {"types": {}}
    for kind_index, kind in enumerate(TYPE_ORDER):
        train_indices = np.asarray([index for index, row in enumerate(train_rows) if row.type == kind])
        target_indices = np.asarray([index for index, row in enumerate(all_rows) if row.type == kind])
        positive = train_indices[[train_rows[index].positive for index in train_indices]]
        unlabeled = train_indices[[not train_rows[index].positive for index in train_indices]]
        diagnostics["types"][kind] = {"positive": len(positive), "unlabeled": len(unlabeled)}
        if len(target_indices) == 0:
            continue
        if len(positive) < 2 or len(unlabeled) < 2:
            constant = 1.0 if len(positive) >= len(unlabeled) and len(positive) else 0.0
            predictions[:, target_indices] = constant
            continue
        for seed in range(seeds):
            rng = np.random.default_rng(2500 + 101 * kind_index + seed)
            chosen = rng.choice(unlabeled, size=len(positive), replace=len(unlabeled) < len(positive))
            indices = np.concatenate([positive, chosen])
            labels = np.concatenate([np.ones(len(positive)), np.zeros(len(chosen))])
            model = make_pipeline(
                StandardScaler(),
                LogisticRegression(C=1.0, max_iter=1500, random_state=seed),
            )
            model.fit(x_train[indices], labels)
            predictions[seed, target_indices] = model.predict_proba(x_all[target_indices])[:, 1]
    return predictions.mean(axis=0), predictions.std(axis=0), diagnostics


def fit_pu_scores(
    x: np.ndarray,
    rows: Sequence[PURow],
    train_records: set[int],
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    train_indices = [index for index, row in enumerate(rows) if row.record in train_records and not row.overlaps_h20]
    candidate_indices = [index for index, row in enumerate(rows) if not row.overlaps_h20]
    train_rows = [rows[index] for index in train_indices]
    candidate_rows = [rows[index] for index in candidate_indices]
    mean, std, diagnostics = _fit_pu_bags(
        x[train_indices], train_rows, x[candidate_indices], candidate_rows
    )
    full_mean = np.zeros(len(rows), dtype=np.float32)
    full_std = np.ones(len(rows), dtype=np.float32)
    full_mean[candidate_indices] = mean
    full_std[candidate_indices] = std
    diagnostics.update({"train_rows": len(train_indices), "candidate_rows": len(candidate_indices)})
    return full_mean, full_std, diagnostics


def _greedy_additions(
    rows: Sequence[PURow],
    scores: np.ndarray,
    records: set[int],
    threshold: float,
) -> dict[int, list[int]]:
    selected: dict[int, list[int]] = defaultdict(list)
    for record in sorted(records):
        candidates = [
            index for index, row in enumerate(rows)
            if row.record == record and not row.overlaps_h20 and scores[index] >= threshold
        ]
        candidates.sort(key=lambda index: (-float(scores[index]), -rows[index].source_count, rows[index].position, rows[index].type))
        intervals: list[tuple[int, int]] = []
        for index in candidates:
            start, end = rows[index].position
            if any(max(start, left) < min(end, right) for left, right in intervals):
                continue
            selected[record].append(index)
            intervals.append((start, end))
    return selected


def _prf(predicted: set[tuple[int, int, str]], gold: set[tuple[int, int, str]]) -> dict[str, float | int]:
    tp = len(predicted & gold)
    fp = len(predicted - gold)
    fn = len(gold - predicted)
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"tp": tp, "fp": fp, "fn": fn, "precision": precision, "recall": recall, "f1": f1}


def evaluate_selection(
    rows: Sequence[PURow],
    scores: np.ndarray,
    records: set[int],
    threshold: float,
    h23_keys: dict[int, set[tuple[int, int, str]]],
    h20_keys: dict[int, set[tuple[int, int, str]]],
) -> dict[str, Any]:
    selected = _greedy_additions(rows, scores, records, threshold)
    predicted: set[tuple[int, int, str, int]] = set()
    baseline: set[tuple[int, int, str, int]] = set()
    gold: set[tuple[int, int, str, int]] = set()
    additions: set[tuple[int, int, str, int]] = set()
    per_type: dict[str, dict[str, Any]] = {}
    for record in records:
        baseline.update((*key, record) for key in h20_keys[record])
        gold.update((*key, record) for key in h23_keys[record])
        additions.update((*rows[index].key, record) for index in selected.get(record, []))
    predicted = baseline | additions
    result = {
        "threshold": threshold,
        "baseline": _prf(baseline, gold),
        "with_additions": _prf(predicted, gold),
        "additions": _prf(additions, gold - baseline),
        "selected_additions": len(additions),
        "per_type": per_type,
    }
    for kind in TYPE_ORDER:
        p = {key for key in predicted if key[2] == kind}
        g = {key for key in gold if key[2] == kind}
        b = {key for key in baseline if key[2] == kind}
        per_type[kind] = {"baseline": _prf(b, g), "with_additions": _prf(p, g)}
    return result


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    a, b = set(left), set(right)
    return len(a & b) / len(a | b) if a or b else 1.0


def assertion_report(
    rows: Sequence[PURow],
    x: np.ndarray,
    train_records: set[int],
    eval_records: set[int],
    h23_dir: str | Path,
    input_dir: str | Path,
) -> dict[str, Any]:
    h23, inputs = Path(h23_dir), Path(input_dir)
    gold_by_record: dict[int, dict[tuple[int, int, str], tuple[str, ...]]] = {}
    for record in train_records | eval_records:
        values = _load_json_entities(h23 / f"{record}.json")
        gold_by_record[record] = {
            _entity_key(value): tuple(value.get("assertions") or ()) for value in values
        }
    positive_indices = [index for index, row in enumerate(rows) if row.positive]
    train_indices = [index for index in positive_indices if rows[index].record in train_records]
    eval_indices = [index for index in positive_indices if rows[index].record in eval_records]
    predictions: dict[int, set[str]] = {index: set() for index in eval_indices}
    label_diagnostics: dict[str, Any] = {}
    for assertion in ASSERTION_ORDER:
        labels = np.asarray([
            assertion in gold_by_record[rows[index].record][rows[index].key]
            for index in train_indices
        ], dtype=int)
        positives = int(labels.sum())
        negatives = int(len(labels) - positives)
        label_diagnostics[assertion] = {"positive": positives, "negative": negatives}
        if positives < 8 or negatives < 8:
            continue
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(C=1.0, max_iter=1500, class_weight="balanced", random_state=444),
        )
        model.fit(x[train_indices], labels)
        probabilities = model.predict_proba(x[eval_indices])[:, 1]
        for index, probability in zip(eval_indices, probabilities):
            if probability >= 0.5:
                predictions[index].add(assertion)
    learned_scores: list[float] = []
    rule_scores: list[float] = []
    learned_exact = rule_exact = 0
    for index in eval_indices:
        row = rows[index]
        gold = set(gold_by_record[row.record][row.key])
        raw = (inputs / f"{row.record}.txt").read_text(encoding="utf-8")
        rule = set(infer_assertions(Entity(text=row.text, type=row.type, position=row.position), raw))
        learned = predictions[index]
        # Registered fallback applies label-wise when a class lacks support.
        for assertion in ASSERTION_ORDER:
            diag = label_diagnostics[assertion]
            if diag["positive"] < 8 or diag["negative"] < 8:
                if assertion in rule:
                    learned.add(assertion)
                else:
                    learned.discard(assertion)
        learned_scores.append(_jaccard(learned, gold))
        rule_scores.append(_jaccard(rule, gold))
        learned_exact += int(learned == gold)
        rule_exact += int(rule == gold)
    count = len(eval_indices)
    return {
        "rows": count,
        "labels": label_diagnostics,
        "learned_macro_jaccard": float(np.mean(learned_scores)) if count else 0.0,
        "rule_macro_jaccard": float(np.mean(rule_scores)) if count else 0.0,
        "learned_exact_set_accuracy": learned_exact / count if count else 0.0,
        "rule_exact_set_accuracy": rule_exact / count if count else 0.0,
    }


def _ece(scores: np.ndarray, rows: Sequence[PURow], records: set[int], bins: int = 10) -> float:
    indices = [index for index, row in enumerate(rows) if row.record in records and not row.overlaps_h20]
    if not indices:
        return 0.0
    probabilities = scores[indices]
    labels = np.asarray([rows[index].positive for index in indices], dtype=float)
    total = len(indices)
    value = 0.0
    for left in np.linspace(0, 1, bins, endpoint=False):
        right = left + 1 / bins
        mask = (probabilities >= left) & (probabilities < right if right < 1 else probabilities <= right)
        if mask.any():
            value += mask.sum() / total * abs(probabilities[mask].mean() - labels[mask].mean())
    return float(value)


def run_experiment(
    input_dir: str | Path,
    h23_dir: str | Path,
    h20_dir: str | Path,
    proposal_dirs: Sequence[str | Path],
    output_dir: str | Path,
    *,
    cache_path: str | Path | None = None,
) -> dict[str, Any]:
    train_records, dev_records, test_records = set(DEFAULT_TRAIN), set(DEFAULT_DEV), set(DEFAULT_TEST)
    rows, h23_keys, h20_keys = collect_rows(input_dir, h23_dir, h20_dir, proposal_dirs)
    structured = structured_features(rows)
    variants: dict[str, np.ndarray] = {"structured": structured}
    embedding_meta: dict[str, Any] | None = None
    if cache_path is not None:
        embeddings, embedding_meta = cached_ollama_embeddings(
            [row.context for row in rows], cache_path, batch_size=128,
            progress=lambda done, total: print(f"H25 embeddings {done}/{total}", flush=True),
        )
        train_indices = [index for index, row in enumerate(rows) if row.record in train_records]
        components = min(64, len(train_indices) - 1, embeddings.shape[1] - 1)
        reducer = TruncatedSVD(n_components=components, random_state=2501)
        reducer.fit(embeddings[train_indices])
        reduced = reducer.transform(embeddings).astype(np.float32)
        variants["contextual"] = np.concatenate([structured, reduced], axis=1)
        embedding_meta = {**embedding_meta, "svd_components": components,
                          "svd_explained_variance": float(reducer.explained_variance_ratio_.sum())}
    reports: dict[str, Any] = {}
    scored: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    selections: list[tuple[float, float, int, str, dict[str, Any]]] = []
    for name, features in variants.items():
        mean, std, diagnostics = fit_pu_scores(features, rows, train_records)
        scored[name] = (mean, std)
        dev_grid = [evaluate_selection(rows, mean, dev_records, threshold, h23_keys, h20_keys)
                    for threshold in (0.80, 0.90, 0.95)]
        reports[name] = {
            "diagnostics": diagnostics,
            "dev_grid": dev_grid,
            "dev_ece_against_pseudo_labels": _ece(mean, rows, dev_records),
        }
        for result in dev_grid:
            selections.append((
                float(result["with_additions"]["f1"]),
                float(result["threshold"]),
                int(name == "structured"),
                name,
                result,
            ))
    _, selected_threshold, _, selected_name, selected_dev = max(selections)
    selected_scores, selected_std = scored[selected_name]
    selected_test = evaluate_selection(
        rows, selected_scores, test_records, selected_threshold, h23_keys, h20_keys
    )
    assertion_dev = assertion_report(rows, variants[selected_name], train_records, dev_records, h23_dir, input_dir)
    assertion_test = assertion_report(rows, variants[selected_name], train_records, test_records, h23_dir, input_dir)
    oracle_scores = np.asarray([
        1.0 if row.positive and not row.overlaps_h20 else 0.0 for row in rows
    ], dtype=np.float32)
    oracle = {
        "dev": evaluate_selection(rows, oracle_scores, dev_records, 0.5, h23_keys, h20_keys),
        "test": evaluate_selection(rows, oracle_scores, test_records, 0.5, h23_keys, h20_keys),
    }
    structured_best = max(
        reports["structured"]["dev_grid"],
        key=lambda result: (result["with_additions"]["f1"], result["threshold"]),
    )
    contextual_gain = None
    if "contextual" in reports:
        contextual_best = max(
            reports["contextual"]["dev_grid"],
            key=lambda result: (result["with_additions"]["f1"], result["threshold"]),
        )
        contextual_gain = contextual_best["with_additions"]["f1"] - structured_best["with_additions"]["f1"]
    additions_precision_dev = float(selected_dev["additions"]["precision"])
    additions_precision_test = float(selected_test["additions"]["precision"])
    f1_gain_dev = 100 * (selected_dev["with_additions"]["f1"] - selected_dev["baseline"]["f1"])
    f1_gain_test = 100 * (selected_test["with_additions"]["f1"] - selected_test["baseline"]["f1"])
    type_losses = []
    for result in (selected_dev, selected_test):
        type_losses.extend(
            100 * (metrics["with_additions"]["f1"] - metrics["baseline"]["f1"])
            for metrics in result["per_type"].values()
        )
    gates = {
        "f1_gain_dev_at_least_3": f1_gain_dev >= 3,
        "f1_gain_test_at_least_3": f1_gain_test >= 3,
        "addition_precision_dev_at_least_0_75": additions_precision_dev >= 0.75,
        "addition_precision_test_at_least_0_75": additions_precision_test >= 0.75,
        "no_type_loses_more_than_2": min(type_losses, default=0.0) >= -2,
        "assertion_dev_gain_at_least_0_03": assertion_dev["learned_macro_jaccard"] - assertion_dev["rule_macro_jaccard"] >= 0.03,
        "assertion_test_gain_at_least_0_03": assertion_test["learned_macro_jaccard"] - assertion_test["rule_macro_jaccard"] >= 0.03,
        "contextual_gain_at_least_0_01_or_rejected": selected_name == "structured" or (contextual_gain or 0.0) >= 0.01,
    }
    beyond_h23 = [
        {
            "record": row.record,
            "text": row.text,
            "type": row.type,
            "position": list(row.position),
            "sources": sorted(row.confidences),
            "score": float(selected_scores[index]),
            "std": float(selected_std[index]),
        }
        for index, row in enumerate(rows)
        if not row.positive and not row.overlaps_h20 and row.source_count >= 2
        and selected_scores[index] >= 0.95 and selected_std[index] <= 0.08
    ]
    report = {
        "label_warning": "H23 is an externally useful pseudo target, not organizer ground truth.",
        "rows": len(rows),
        "positive_rows": sum(row.positive for row in rows),
        "unlabeled_rows": sum(not row.positive for row in rows),
        "variants": reports,
        "selected": {"variant": selected_name, "threshold": selected_threshold,
                     "dev": selected_dev, "test": selected_test},
        "assertions": {"dev": assertion_dev, "test": assertion_test},
        "proposal_pool_oracle": oracle,
        "contextual_dev_f1_gain": contextual_gain,
        "gates": gates,
        "all_gates_pass": all(gates.values()),
        "beyond_h23_high_stability": beyond_h23,
        "embedding": embedding_meta,
    }
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="turn2/input")
    parser.add_argument("--h23", default="turn2/output_v8_candidate_semantic")
    parser.add_argument("--h20", default="turn2/output_v6_expanded_pair")
    parser.add_argument("--proposals", nargs=3, default=[
        "experiments/H_turn2_multimodel_core/proposals_vietmed",
        "experiments/H_turn2_multimodel_core/proposals_bami_v15",
        "experiments/H_turn2_multimodel_core/proposals_bami_v3",
    ])
    parser.add_argument("--output", default="experiments/H25_pu_span_assertion/results")
    parser.add_argument("--cache", default="experiments/H25_pu_span_assertion/cache/context_embeddings.npy")
    parser.add_argument("--structured-only", action="store_true")
    args = parser.parse_args()
    report = run_experiment(
        args.input, args.h23, args.h20, args.proposals, args.output,
        cache_path=None if args.structured_only else args.cache,
    )
    print(json.dumps({"selected": report["selected"], "assertions": report["assertions"],
                      "gates": report["gates"], "beyond_h23": len(report["beyond_h23_high_stability"])},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
