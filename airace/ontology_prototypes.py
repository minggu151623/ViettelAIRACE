from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from .ontology_dense import _metric_block, rank_type_restricted


def build_train_prototypes(
    rows: list[dict[str, Any]],
    mention_embeddings: np.ndarray,
    concept_ids: list[str],
) -> tuple[np.ndarray, dict[str, int]]:
    """Return one normalized train-only clinical prototype per linked concept."""

    concept_index = {identifier: index for index, identifier in enumerate(concept_ids)}
    sums: dict[str, np.ndarray] = {}
    counts: dict[str, int] = defaultdict(int)
    for row_index, row in enumerate(rows):
        if row["fold"] != "train":
            continue
        for identifier in row["gold_concepts"]:
            if identifier not in concept_index:
                continue
            if identifier not in sums:
                sums[identifier] = np.zeros(mention_embeddings.shape[1], dtype=np.float64)
            sums[identifier] += mention_embeddings[row_index].astype(np.float64)
            counts[identifier] += 1
    prototypes = np.zeros((len(concept_ids), mention_embeddings.shape[1]), dtype=np.float32)
    for identifier, total in sums.items():
        vector = total / counts[identifier]
        vector /= max(float(np.linalg.norm(vector)), 1e-12)
        prototypes[concept_index[identifier]] = vector.astype(np.float32)
    return prototypes, dict(counts)


def replace_seen_concepts(
    canonical_embeddings: np.ndarray,
    prototypes: np.ndarray,
    prototype_counts: dict[str, int],
    concept_ids: list[str],
) -> np.ndarray:
    if canonical_embeddings.shape != prototypes.shape:
        raise ValueError("canonical embeddings and prototypes must have the same shape")
    result = canonical_embeddings.astype(np.float32, copy=True)
    for index, identifier in enumerate(concept_ids):
        if prototype_counts.get(identifier, 0):
            result[index] = prototypes[index]
    result /= np.maximum(np.linalg.norm(result, axis=1, keepdims=True), 1e-12)
    return result


def _evaluate_subset(
    rows: list[dict[str, Any]],
    indices: list[int],
    mention_embeddings: np.ndarray,
    concept_embeddings: np.ndarray,
    concept_ids: list[str],
) -> tuple[dict[str, Any], list[list[str]]]:
    selected = [rows[index] for index in indices]
    rankings = rank_type_restricted(
        mention_embeddings[indices],
        [row["type"] for row in selected],
        concept_embeddings,
        concept_ids,
    )
    return _metric_block(selected, rankings), rankings


def clinical_prototype_retrieval(
    dataset: dict[str, Any],
    concept_ids: list[str],
    canonical_embeddings: np.ndarray,
    mention_embeddings: np.ndarray,
) -> dict[str, Any]:
    rows = dataset["rows"]
    prototypes, counts = build_train_prototypes(rows, mention_embeddings, concept_ids)
    candidate_embeddings = replace_seen_concepts(
        canonical_embeddings, prototypes, counts, concept_ids
    )
    train_concepts = set(counts)
    report: dict[str, Any] = {
        "method": "frozen_bami_train_only_clinical_prototypes",
        "weak_label_warning": dataset["label_status"],
        "fitted_parameters": 0,
        "prototype_concepts": len(counts),
        "prototype_train_rows": sum(row["fold"] == "train" for row in rows),
        "folds": {},
        "seen_vs_unseen": {},
        "predictions": [],
    }
    for fold in ("train", "dev", "test"):
        indices = [index for index, row in enumerate(rows) if row["fold"] == fold]
        metrics, rankings = _evaluate_subset(
            rows, indices, mention_embeddings, candidate_embeddings, concept_ids
        )
        report["folds"][fold] = metrics
        for index, ranking in zip(indices, rankings):
            report["predictions"].append(
                {
                    "id": rows[index]["id"],
                    "fold": fold,
                    "gold": rows[index]["gold_concepts"],
                    "top10": ranking,
                }
            )
    for fold in ("dev", "test"):
        for status in ("seen", "unseen"):
            indices = []
            for index, row in enumerate(rows):
                if row["fold"] != fold:
                    continue
                is_seen = bool(set(row["gold_concepts"]) & train_concepts)
                if is_seen == (status == "seen"):
                    indices.append(index)
            metrics, _ = _evaluate_subset(
                rows, indices, mention_embeddings, candidate_embeddings, concept_ids
            )
            report["seen_vs_unseen"][f"{fold}_{status}"] = metrics
    return report


def save_prototype_report(report: dict[str, Any], output_path: str | Path) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
