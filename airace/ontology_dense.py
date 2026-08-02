from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer

from .ontology_graph import OntologyGraph


def _file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def choose_device(requested: str = "auto") -> torch.device:
    if requested != "auto":
        return torch.device(requested)
    if torch.cuda.is_available():
        return torch.device("cuda")
    if torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def load_token_backbone(model_path: str | Path, device: torch.device):
    """Load the trained token model and expose only its exact base encoder."""

    model = AutoModelForTokenClassification.from_pretrained(
        str(model_path), local_files_only=True
    )
    backbone = getattr(model, model.base_model_prefix)
    backbone.eval().to(device)
    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
    return tokenizer, backbone


def encode_texts(
    texts: Iterable[str],
    tokenizer,
    backbone,
    device: torch.device,
    *,
    batch_size: int = 192,
    max_length: int = 48,
) -> np.ndarray:
    values = list(texts)
    chunks: list[np.ndarray] = []
    with torch.inference_mode():
        for offset in range(0, len(values), batch_size):
            batch = tokenizer(
                values[offset:offset + batch_size],
                padding=True,
                truncation=True,
                max_length=max_length,
                return_tensors="pt",
            )
            batch = {key: value.to(device) for key, value in batch.items()}
            # PhoBERT-style backbones do not consume token_type_ids.
            batch.pop("token_type_ids", None)
            output = backbone(**batch)
            mask = batch["attention_mask"].unsqueeze(-1).to(output.last_hidden_state.dtype)
            pooled = (output.last_hidden_state * mask).sum(1) / mask.sum(1).clamp_min(1)
            pooled = torch.nn.functional.normalize(pooled, dim=-1)
            chunks.append(pooled.float().cpu().numpy())
    if not chunks:
        hidden = int(backbone.config.hidden_size)
        return np.empty((0, hidden), dtype=np.float32)
    return np.concatenate(chunks).astype(np.float32, copy=False)


def rank_type_restricted(
    query_embeddings: np.ndarray,
    query_types: list[str],
    concept_embeddings: np.ndarray,
    concept_ids: list[str],
    *,
    top_k: int = 10,
) -> list[list[str]]:
    pools = {
        "CHẨN_ĐOÁN": np.asarray(
            [index for index, identifier in enumerate(concept_ids) if identifier.startswith("ICD:")],
            dtype=np.int64,
        ),
        "THUỐC": np.asarray(
            [index for index, identifier in enumerate(concept_ids) if identifier.startswith("RX:")],
            dtype=np.int64,
        ),
    }
    rankings: list[list[str]] = []
    for query, kind in zip(query_embeddings, query_types):
        pool = pools[kind]
        scores = concept_embeddings[pool] @ query
        count = min(top_k, len(pool))
        selected = np.argpartition(scores, -count)[-count:]
        selected = sorted(selected, key=lambda index: (-float(scores[index]), concept_ids[pool[index]]))
        rankings.append([concept_ids[pool[index]] for index in selected])
    return rankings


def _metric_block(rows: list[dict[str, Any]], rankings: list[list[str]]) -> dict[str, Any]:
    hits = {1: 0, 5: 0, 10: 0}
    type_hits: dict[str, dict[int, int]] = defaultdict(lambda: {1: 0, 5: 0, 10: 0})
    type_total: dict[str, int] = defaultdict(int)
    for row, ranked in zip(rows, rankings):
        gold = set(row["gold_concepts"])
        kind = row["type"]
        type_total[kind] += 1
        for k in hits:
            matched = bool(gold.intersection(ranked[:k]))
            hits[k] += int(matched)
            type_hits[kind][k] += int(matched)
    total = len(rows) or 1
    return {
        "queries": len(rows),
        "recall": {f"@{k}": hits[k] / total for k in sorted(hits)},
        "recall_by_type": {
            kind: {f"@{k}": values[k] / type_total[kind] for k in sorted(values)}
            for kind, values in sorted(type_hits.items())
        },
    }


def dense_retrieval_baseline(
    graph: OntologyGraph,
    dataset: dict[str, Any],
    model_path: str | Path,
    cache_dir: str | Path,
    *,
    device: str = "auto",
    batch_size: int = 192,
    max_length: int = 48,
) -> dict[str, Any]:
    model_path, cache_dir = Path(model_path), Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    model_hash = _file_sha256(model_path / "model.safetensors")
    graph_hash = str(graph.manifest()["node_sha256"])
    cache_key = hashlib.sha256(f"{model_hash}:{graph_hash}:{max_length}".encode()).hexdigest()[:20]
    embedding_path = cache_dir / f"concept_embeddings_{cache_key}.npy"
    identifiers_path = cache_dir / f"concept_ids_{cache_key}.json"
    concept_ids = sorted(graph.nodes)
    torch_device = choose_device(device)
    tokenizer, backbone = load_token_backbone(model_path, torch_device)
    cache_hit = embedding_path.exists() and identifiers_path.exists()
    if cache_hit:
        stored_ids = json.loads(identifiers_path.read_text(encoding="utf-8"))
        cache_hit = stored_ids == concept_ids
    if cache_hit:
        concept_embeddings = np.load(embedding_path).astype(np.float32)
    else:
        concept_embeddings = encode_texts(
            [graph.nodes[identifier].canonical for identifier in concept_ids],
            tokenizer,
            backbone,
            torch_device,
            batch_size=batch_size,
            max_length=max_length,
        )
        np.save(embedding_path, concept_embeddings.astype(np.float16))
        identifiers_path.write_text(
            json.dumps(concept_ids, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    # Float16 cache roundoff slightly changes norms; restore unit length.
    denominator = np.linalg.norm(concept_embeddings, axis=1, keepdims=True)
    concept_embeddings = concept_embeddings / np.maximum(denominator, 1e-12)
    rows = dataset["rows"]
    query_embeddings = encode_texts(
        [row["mention"] for row in rows],
        tokenizer,
        backbone,
        torch_device,
        batch_size=batch_size,
        max_length=max_length,
    )
    rankings = rank_type_restricted(
        query_embeddings,
        [row["type"] for row in rows],
        concept_embeddings,
        concept_ids,
    )
    report = {
        "method": "unadapted_bami_mean_pool_dense",
        "weak_label_warning": dataset["label_status"],
        "model_path": str(model_path),
        "model_sha256": model_hash,
        "graph_node_sha256": graph_hash,
        "device": str(torch_device),
        "batch_size": batch_size,
        "max_length": max_length,
        "concept_nodes": len(concept_ids),
        "cache_hit": cache_hit,
        "all": _metric_block(rows, rankings),
        "folds": {},
        "predictions": [],
    }
    for fold in ("train", "dev", "test"):
        indices = [index for index, row in enumerate(rows) if row["fold"] == fold]
        report["folds"][fold] = _metric_block(
            [rows[index] for index in indices], [rankings[index] for index in indices]
        )
    for row, ranked in zip(rows, rankings):
        report["predictions"].append(
            {"id": row["id"], "fold": row["fold"], "gold": row["gold_concepts"], "top10": ranked}
        )
    return report

