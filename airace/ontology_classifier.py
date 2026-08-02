from __future__ import annotations

import difflib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .normalize import normalize_key
from .ontology_dense import _metric_block
from .ontology_graph import OntologyGraph


SEMANTIC_FEATURES = (
    "reciprocal_qwen_rank",
    "reciprocal_lexical_rank",
    "reciprocal_router_rank",
    "qwen_mention_title_cosine",
    "qwen_context_title_cosine",
    "normalized_alias_sequence_similarity",
    "exact_normalized_alias_match",
    "code_specificity",
    "entity_type_is_drug",
)
GRAPH_FEATURES = (
    "log_direct_degree",
    "direct_neighbors_inside_candidate_pool",
    "has_parent_inside_candidate_pool",
    "has_child_inside_candidate_pool",
)


def stable_candidate_union(qwen: list[str], lexical: list[str]) -> list[str]:
    result: list[str] = []
    for identifier in qwen + lexical:
        if identifier not in result:
            result.append(identifier)
    return result


def _ranks(report: dict[str, Any]) -> dict[int, list[str]]:
    return {row["id"]: row["top10"] for row in report["predictions"]}


def _undirected_neighbors(graph: OntologyGraph) -> dict[str, set[str]]:
    result = {identifier: set() for identifier in graph.nodes}
    for edge in graph.edges:
        result[edge.source].add(edge.target)
        result[edge.target].add(edge.source)
    return result


@dataclass
class CandidateFeatureTable:
    matrix: np.ndarray
    labels: np.ndarray
    row_ids: np.ndarray
    identifiers: list[str]
    original_ranks: np.ndarray
    feature_names: tuple[str, ...]
    row_pools: dict[int, list[str]]


def build_candidate_features(
    dataset: dict[str, Any],
    graph: OntologyGraph,
    qwen_report: dict[str, Any],
    lexical_report: dict[str, Any],
    router_report: dict[str, Any],
    concept_ids: list[str],
    concept_embeddings: np.ndarray,
    mention_embeddings: np.ndarray,
    context_embeddings: np.ndarray,
) -> CandidateFeatureTable:
    concept_index = {identifier: index for index, identifier in enumerate(concept_ids)}
    qwen, lexical, router = _ranks(qwen_report), _ranks(lexical_report), _ranks(router_report)
    neighbors = _undirected_neighbors(graph)
    outgoing: dict[str, list[tuple[str, str]]] = {identifier: [] for identifier in graph.nodes}
    for edge in graph.edges:
        outgoing[edge.source].append((edge.relation, edge.target))
    values: list[list[float]] = []
    labels: list[int] = []
    row_ids: list[int] = []
    identifiers: list[str] = []
    original_ranks: list[int] = []
    row_pools: dict[int, list[str]] = {}
    for row_position, row in enumerate(dataset["rows"]):
        pool = stable_candidate_union(qwen[row["id"]], lexical[row["id"]])
        row_pools[row["id"]] = pool
        pool_set = set(pool)
        normalized_mention = normalize_key(row["mention"])
        qrank = {identifier: rank + 1 for rank, identifier in enumerate(qwen[row["id"]])}
        lrank = {identifier: rank + 1 for rank, identifier in enumerate(lexical[row["id"]])}
        rrank = {identifier: rank + 1 for rank, identifier in enumerate(router[row["id"]])}
        gold = set(row["gold_concepts"])
        for original_rank, identifier in enumerate(pool):
            node = graph.nodes[identifier]
            node_index = concept_index[identifier]
            aliases = {normalize_key(node.canonical)} | {normalize_key(alias) for alias in node.aliases}
            alias_similarity = max(
                (difflib.SequenceMatcher(None, normalized_mention, alias).ratio() for alias in aliases),
                default=0.0,
            )
            relations = outgoing[identifier]
            code_specificity = float(
                (identifier.startswith("ICD:") and "." in identifier)
                or (identifier.startswith("RX:") and node.semantic_type not in {"IN", "PIN", "MIN"})
            )
            semantic = [
                1.0 / qrank[identifier] if identifier in qrank else 0.0,
                1.0 / lrank[identifier] if identifier in lrank else 0.0,
                1.0 / rrank[identifier] if identifier in rrank else 0.0,
                float(mention_embeddings[row_position] @ concept_embeddings[node_index]),
                float(context_embeddings[row_position] @ concept_embeddings[node_index]),
                alias_similarity,
                float(normalized_mention in aliases),
                code_specificity,
                float(row["type"] == "THUỐC"),
            ]
            graph_values = [
                math.log1p(len(neighbors[identifier])),
                float(len(neighbors[identifier] & pool_set)),
                float(any(relation == "icd_parent" and target in pool_set for relation, target in relations)),
                float(any(relation == "icd_child" and target in pool_set for relation, target in relations)),
            ]
            values.append(semantic + graph_values)
            labels.append(int(identifier in gold))
            row_ids.append(row["id"])
            identifiers.append(identifier)
            original_ranks.append(original_rank)
    return CandidateFeatureTable(
        matrix=np.asarray(values, dtype=np.float32),
        labels=np.asarray(labels, dtype=np.int64),
        row_ids=np.asarray(row_ids, dtype=np.int64),
        identifiers=identifiers,
        original_ranks=np.asarray(original_ranks, dtype=np.int64),
        feature_names=SEMANTIC_FEATURES + GRAPH_FEATURES,
        row_pools=row_pools,
    )


def _eligible_training_mask(
    table: CandidateFeatureTable, dataset: dict[str, Any]
) -> np.ndarray:
    train_ids = {row["id"] for row in dataset["rows"] if row["fold"] == "train"}
    positive_groups = {
        int(row_id)
        for row_id, label in zip(table.row_ids, table.labels)
        if int(row_id) in train_ids and label == 1
    }
    return np.asarray([int(row_id) in positive_groups for row_id in table.row_ids], dtype=bool)


def fit_classifier(
    table: CandidateFeatureTable,
    dataset: dict[str, Any],
    *,
    include_graph: bool,
    seed: int = 2402,
) -> Pipeline:
    mask = _eligible_training_mask(table, dataset)
    width = len(table.feature_names) if include_graph else len(SEMANTIC_FEATURES)
    pipeline = Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    C=1.0,
                    class_weight="balanced",
                    max_iter=2000,
                    random_state=seed,
                ),
            ),
        ]
    )
    pipeline.fit(table.matrix[mask, :width], table.labels[mask])
    return pipeline


def evaluate_classifier(
    pipeline: Pipeline,
    table: CandidateFeatureTable,
    dataset: dict[str, Any],
    *,
    fold: str,
    include_graph: bool,
) -> dict[str, Any]:
    fold_ids = {row["id"] for row in dataset["rows"] if row["fold"] == fold}
    mask = np.asarray([int(row_id) in fold_ids for row_id in table.row_ids], dtype=bool)
    width = len(table.feature_names) if include_graph else len(SEMANTIC_FEATURES)
    scores = pipeline.predict_proba(table.matrix[mask, :width])[:, 1]
    grouped: dict[int, list[tuple[float, int, str]]] = {}
    for row_id, identifier, rank, score in zip(
        table.row_ids[mask],
        np.asarray(table.identifiers, dtype=object)[mask],
        table.original_ranks[mask],
        scores,
    ):
        grouped.setdefault(int(row_id), []).append((float(score), int(rank), str(identifier)))
    rows = [row for row in dataset["rows"] if row["fold"] == fold]
    rankings: list[list[str]] = []
    predictions: list[dict[str, Any]] = []
    for row in rows:
        ordered = sorted(grouped[row["id"]], key=lambda value: (-value[0], value[1], value[2]))
        ranking = [identifier for _, _, identifier in ordered]
        rankings.append(ranking)
        predictions.append(
            {
                "id": row["id"],
                "fold": fold,
                "gold": row["gold_concepts"],
                "top20": ranking,
                "scores": [score for score, _, _ in ordered],
            }
        )
    return {
        "fold": fold,
        "variant": "semantic_plus_graph" if include_graph else "semantic_only",
        "metrics": _metric_block(rows, rankings),
        "predictions": predictions,
    }


def classifier_coefficients(pipeline: Pipeline, feature_names: tuple[str, ...]) -> dict[str, float]:
    classifier = pipeline.named_steps["classifier"]
    return {
        name: float(value)
        for name, value in zip(feature_names, classifier.coef_[0])
    }


def save_classifier_report(report: dict[str, Any], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
