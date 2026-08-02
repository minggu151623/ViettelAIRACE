from __future__ import annotations

import copy
import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor, nn

from .ontology_dense import (
    _metric_block,
    choose_device,
    encode_texts,
    load_token_backbone,
    rank_type_restricted,
)
from .ontology_graph import OntologyGraph


class FeatureProjection(nn.Module):
    def __init__(self, input_size: int, output_size: int):
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(input_size, output_size),
            nn.GELU(),
            nn.LayerNorm(output_size),
        )

    def forward(self, values: Tensor) -> Tensor:
        return torch.nn.functional.normalize(self.layers(values), dim=-1)


class AlignmentModel(nn.Module):
    def __init__(self, mention_size: int, concept_size: int, embedding_size: int):
        super().__init__()
        self.mention_projection = FeatureProjection(mention_size, embedding_size)
        self.concept_projection = FeatureProjection(concept_size, embedding_size)


def _multi_positive_loss(logits: Tensor, positive_mask: Tensor) -> Tensor:
    log_prob = logits.log_softmax(dim=-1)
    selected = log_prob.masked_fill(~positive_mask, -torch.inf)
    valid = positive_mask.any(dim=-1)
    if not bool(valid.any()):
        return logits.sum() * 0
    return -torch.logsumexp(selected[valid], dim=-1).mean()


def _sha256_array(values: np.ndarray) -> str:
    digest = hashlib.sha256()
    view = np.ascontiguousarray(values).view(np.uint8)
    for offset in range(0, view.size, 1024 * 1024):
        digest.update(view[offset:offset + 1024 * 1024])
    return digest.hexdigest()


def build_neighbor_features(
    graph: OntologyGraph,
    concept_ids: list[str],
    base_embeddings: np.ndarray,
    cache_path: str | Path,
    *,
    chunk_size: int = 4096,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Mean direct-neighbour embeddings, computed in bounded CPU chunks."""

    cache_path = Path(cache_path)
    metadata_path = cache_path.with_suffix(".json")
    source_hash = _sha256_array(base_embeddings)
    if cache_path.exists() and metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if metadata.get("source_embedding_sha256") == source_hash:
            return np.load(cache_path).astype(np.float32), {**metadata, "cache_hit": True}
    index = {identifier: position for position, identifier in enumerate(concept_ids)}
    source_indices: list[int] = []
    target_indices: list[int] = []
    for edge in graph.edges:
        source = index.get(edge.source)
        target = index.get(edge.target)
        if source is not None and target is not None:
            source_indices.append(source)
            target_indices.append(target)
    aggregate = np.zeros(base_embeddings.shape, dtype=np.float32)
    degree = np.zeros(len(concept_ids), dtype=np.int32)
    for offset in range(0, len(source_indices), chunk_size):
        sources = np.asarray(source_indices[offset:offset + chunk_size], dtype=np.int64)
        targets = np.asarray(target_indices[offset:offset + chunk_size], dtype=np.int64)
        np.add.at(aggregate, targets, base_embeddings[sources].astype(np.float32))
        np.add.at(degree, targets, 1)
    aggregate /= np.maximum(degree, 1)[:, None]
    norms = np.linalg.norm(aggregate, axis=1, keepdims=True)
    aggregate /= np.maximum(norms, 1e-12)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache_path, aggregate.astype(np.float16))
    metadata = {
        "source_embedding_sha256": source_hash,
        "neighbor_embedding_sha256": _sha256_array(aggregate.astype(np.float16)),
        "nodes": len(concept_ids),
        "edges_aggregated": len(source_indices),
        "nodes_with_neighbors": int((degree > 0).sum()),
        "cache_hit": False,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return aggregate, metadata


def _hard_negative_map(graph: OntologyGraph) -> dict[str, tuple[str, ...]]:
    adjacency = graph.adjacency()
    result: dict[str, tuple[str, ...]] = {}
    for identifier in graph.nodes:
        values = set(adjacency.get(identifier, set()))
        if identifier.startswith("ICD:"):
            values.update(graph.icd_siblings(identifier))
        values = {value for value in values if value.split(":", 1)[0] == identifier.split(":", 1)[0]}
        result[identifier] = tuple(sorted(values))
    return result


def _feature_matrix(
    base_embeddings: np.ndarray,
    neighbor_embeddings: np.ndarray | None,
) -> np.ndarray:
    if neighbor_embeddings is None:
        return base_embeddings.astype(np.float32, copy=False)
    return np.concatenate(
        (base_embeddings.astype(np.float32), neighbor_embeddings.astype(np.float32)), axis=1
    )


def _project_numpy(
    projection: nn.Module,
    values: np.ndarray,
    device: torch.device,
    batch_size: int = 4096,
) -> np.ndarray:
    outputs: list[np.ndarray] = []
    projection.eval()
    with torch.inference_mode():
        for offset in range(0, len(values), batch_size):
            batch = torch.from_numpy(values[offset:offset + batch_size]).to(device)
            outputs.append(projection(batch).float().cpu().numpy())
    return np.concatenate(outputs) if outputs else np.empty((0, 0), dtype=np.float32)


def _evaluate(
    model: AlignmentModel,
    rows: list[dict[str, Any]],
    row_indices: list[int],
    mention_features: np.ndarray,
    concept_features: np.ndarray,
    concept_ids: list[str],
    hard_negatives: dict[str, tuple[str, ...]],
    device: torch.device,
) -> dict[str, Any]:
    selected_rows = [rows[index] for index in row_indices]
    mention_projected = _project_numpy(
        model.mention_projection, mention_features[row_indices], device
    )
    concept_projected = _project_numpy(model.concept_projection, concept_features, device)
    rankings = rank_type_restricted(
        mention_projected,
        [row["type"] for row in selected_rows],
        concept_projected,
        concept_ids,
    )
    metrics = _metric_block(selected_rows, rankings)
    concept_index = {identifier: index for index, identifier in enumerate(concept_ids)}
    correct = total = 0
    for local, row in enumerate(selected_rows):
        gold_ids = [value for value in row["gold_concepts"] if value in concept_index]
        negatives: set[str] = set()
        for gold in gold_ids:
            negatives.update(hard_negatives.get(gold, ()))
        negatives.difference_update(gold_ids)
        negatives = {value for value in negatives if value in concept_index}
        if not gold_ids or not negatives:
            continue
        query = mention_projected[local]
        positive_score = max(float(concept_projected[concept_index[value]] @ query) for value in gold_ids)
        negative_score = max(float(concept_projected[concept_index[value]] @ query) for value in negatives)
        correct += int(positive_score > negative_score)
        total += 1
    metrics["graph_hard_negative_accuracy"] = correct / total if total else None
    metrics["graph_hard_negative_queries"] = total
    return metrics


def _batches(indices: list[int], rows: list[dict[str, Any]], size: int, rng: random.Random):
    by_type: dict[str, list[int]] = defaultdict(list)
    for index in indices:
        by_type[rows[index]["type"]].append(index)
    batches: list[list[int]] = []
    for values in by_type.values():
        rng.shuffle(values)
        batches.extend(values[offset:offset + size] for offset in range(0, len(values), size))
    rng.shuffle(batches)
    return batches


def train_alignment(
    graph: OntologyGraph,
    dataset: dict[str, Any],
    concept_ids: list[str],
    concept_base_embeddings: np.ndarray,
    mention_base_embeddings: np.ndarray,
    *,
    variant: str,
    neighbor_embeddings: np.ndarray | None = None,
    seed: int = 2402,
    embedding_size: int = 256,
    temperature: float = 0.07,
    epochs_max: int = 120,
    patience: int = 15,
    batch_size: int = 32,
    learning_rate: float = 3e-4,
    weight_decay: float = 0.01,
    gradient_clip_norm: float = 1.0,
    eval_every: int = 5,
    device: str = "auto",
) -> tuple[AlignmentModel, dict[str, Any]]:
    if variant not in {"alignment_only", "graph_hard_negative"}:
        raise ValueError(f"unknown variant: {variant}")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    rows = dataset["rows"]
    train_indices = [index for index, row in enumerate(rows) if row["fold"] == "train"]
    dev_indices = [index for index, row in enumerate(rows) if row["fold"] == "dev"]
    test_indices = [index for index, row in enumerate(rows) if row["fold"] == "test"]
    concept_index = {identifier: index for index, identifier in enumerate(concept_ids)}
    hard_map = _hard_negative_map(graph)
    use_graph = variant == "graph_hard_negative"
    if use_graph and neighbor_embeddings is None:
        raise ValueError("graph variant requires neighbor embeddings")
    concept_features = _feature_matrix(
        concept_base_embeddings, neighbor_embeddings if use_graph else None
    )
    torch_device = choose_device(device)
    model = AlignmentModel(
        mention_base_embeddings.shape[1], concept_features.shape[1], embedding_size
    ).to(torch_device)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=weight_decay
    )
    best_state: dict[str, Tensor] | None = None
    best_key = (-math.inf, -math.inf)
    best_epoch = 0
    stale = 0
    trajectory: list[dict[str, Any]] = []
    for epoch in range(1, epochs_max + 1):
        model.train()
        rng = random.Random(seed + epoch)
        losses: list[float] = []
        for batch_indices in _batches(train_indices, rows, batch_size, rng):
            candidate_ids: set[str] = set()
            positives_by_row: list[set[str]] = []
            negatives_by_row: list[set[str]] = []
            for index in batch_indices:
                positive = {value for value in rows[index]["gold_concepts"] if value in concept_index}
                hard: set[str] = set()
                if use_graph:
                    for value in positive:
                        hard.update(hard_map.get(value, ())[:4])
                    hard.difference_update(positive)
                positives_by_row.append(positive)
                negatives_by_row.append(hard)
                candidate_ids.update(positive)
                candidate_ids.update(hard)
            ordered_candidates = sorted(candidate_ids)
            candidate_position = {value: index for index, value in enumerate(ordered_candidates)}
            mention_tensor = torch.from_numpy(mention_base_embeddings[batch_indices]).to(torch_device)
            concept_tensor = torch.from_numpy(
                concept_features[[concept_index[value] for value in ordered_candidates]]
            ).to(torch_device)
            mention_emb = model.mention_projection(mention_tensor)
            concept_emb = model.concept_projection(concept_tensor)
            logits = mention_emb @ concept_emb.T / temperature
            positive_mask = torch.zeros(logits.shape, dtype=torch.bool, device=torch_device)
            negative_mask = torch.zeros(logits.shape, dtype=torch.bool, device=torch_device)
            for row_index, (positive, hard) in enumerate(zip(positives_by_row, negatives_by_row)):
                for value in positive:
                    positive_mask[row_index, candidate_position[value]] = True
                for value in hard:
                    negative_mask[row_index, candidate_position[value]] = True
            loss = _multi_positive_loss(logits, positive_mask)
            if use_graph and bool(negative_mask.any()):
                positive_scores = logits.masked_fill(~positive_mask, -torch.inf).max(dim=-1).values
                negative_scores = logits.masked_fill(~negative_mask, -torch.inf).max(dim=-1).values
                valid = negative_mask.any(dim=-1)
                margin = torch.relu(0.2 - positive_scores[valid] + negative_scores[valid]).mean()
                loss = loss + 0.5 * margin
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), gradient_clip_norm)
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
        if epoch % eval_every != 0 and epoch != epochs_max:
            continue
        dev = _evaluate(
            model,
            rows,
            dev_indices,
            mention_base_embeddings,
            concept_features,
            concept_ids,
            hard_map,
            torch_device,
        )
        key = (dev["recall"]["@1"], dev["recall"]["@5"])
        trajectory.append(
            {
                "epoch": epoch,
                "train_loss": sum(losses) / max(len(losses), 1),
                "dev_recall": dev["recall"],
                "dev_graph_hard_negative_accuracy": dev["graph_hard_negative_accuracy"],
            }
        )
        if key > best_key:
            best_key = key
            best_epoch = epoch
            best_state = copy.deepcopy(model.state_dict())
            stale = 0
        else:
            stale += eval_every
        if stale >= patience:
            break
    if best_state is None:
        raise RuntimeError("training did not produce a checkpoint")
    model.load_state_dict(best_state)
    dev = _evaluate(
        model, rows, dev_indices, mention_base_embeddings, concept_features,
        concept_ids, hard_map, torch_device
    )
    # Test is intentionally read only after the dev-selected checkpoint is restored.
    test = _evaluate(
        model, rows, test_indices, mention_base_embeddings, concept_features,
        concept_ids, hard_map, torch_device
    )
    train = _evaluate(
        model, rows, train_indices, mention_base_embeddings, concept_features,
        concept_ids, hard_map, torch_device
    )
    train_concepts = {
        concept for index in train_indices for concept in rows[index]["gold_concepts"]
    }
    test_seen = [index for index in test_indices if set(rows[index]["gold_concepts"]) & train_concepts]
    test_unseen = [index for index in test_indices if not set(rows[index]["gold_concepts"]) & train_concepts]
    report = {
        "variant": variant,
        "weak_label_warning": dataset["label_status"],
        "seed": seed,
        "device": str(torch_device),
        "best_epoch": best_epoch,
        "epochs_ran": trajectory[-1]["epoch"],
        "selection": "dev_recall_at_1_then_at_5",
        "train": train,
        "dev": dev,
        "test": test,
        "test_seen_concepts": _evaluate(
            model, rows, test_seen, mention_base_embeddings, concept_features,
            concept_ids, hard_map, torch_device
        ) if test_seen else {"queries": 0},
        "test_unseen_concepts": _evaluate(
            model, rows, test_unseen, mention_base_embeddings, concept_features,
            concept_ids, hard_map, torch_device
        ) if test_unseen else {"queries": 0},
        "trajectory": trajectory,
    }
    return model, report


def prepare_base_features(
    dataset: dict[str, Any],
    model_path: str | Path,
    concept_embedding_path: str | Path,
    concept_ids_path: str | Path,
    *,
    device: str = "auto",
    batch_size: int = 256,
    max_length: int = 48,
) -> tuple[list[str], np.ndarray, np.ndarray]:
    concept_ids = json.loads(Path(concept_ids_path).read_text(encoding="utf-8"))
    concept_embeddings = np.load(concept_embedding_path).astype(np.float32)
    concept_embeddings /= np.maximum(
        np.linalg.norm(concept_embeddings, axis=1, keepdims=True), 1e-12
    )
    torch_device = choose_device(device)
    tokenizer, backbone = load_token_backbone(model_path, torch_device)
    mention_embeddings = encode_texts(
        [row["mention"] for row in dataset["rows"]], tokenizer, backbone,
        torch_device, batch_size=batch_size, max_length=max_length
    )
    return concept_ids, concept_embeddings, mention_embeddings


def save_alignment_model(
    model: AlignmentModel,
    report: dict[str, Any],
    output_dir: str | Path,
) -> None:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output / "projection_heads.pt")
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

