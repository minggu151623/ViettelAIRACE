from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np

from .ontology_dense import _metric_block, rank_type_restricted


QUERY_INSTRUCTION = (
    "Instruct: Retrieve the English ICD-10 or RxNorm concept equivalent to the "
    "Vietnamese clinical mention.\nQuery: "
)


def format_query(mention: str) -> str:
    return QUERY_INSTRUCTION + mention


def _request_embeddings(
    texts: Sequence[str],
    *,
    model: str,
    endpoint: str,
    timeout: float,
    retries: int = 3,
) -> np.ndarray:
    payload = json.dumps({"model": model, "input": list(texts)}).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                parsed = json.load(response)
            values = np.asarray(parsed["embeddings"], dtype=np.float32)
            if values.ndim != 2 or len(values) != len(texts):
                raise ValueError("Ollama returned an invalid embedding batch")
            values /= np.maximum(np.linalg.norm(values, axis=1, keepdims=True), 1e-12)
            return values
        except (OSError, ValueError, KeyError, urllib.error.URLError) as error:
            last_error = error
            if attempt + 1 < retries:
                time.sleep(2**attempt)
    raise RuntimeError(f"Ollama embedding request failed after {retries} attempts") from last_error


def cached_ollama_embeddings(
    texts: Sequence[str],
    cache_path: str | Path,
    *,
    model: str = "qwen3-embedding:0.6b",
    endpoint: str = "http://127.0.0.1:11434/api/embed",
    batch_size: int = 256,
    timeout: float = 600,
    progress: Callable[[int, int], None] | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Embed deterministically with a resumable float16 cache."""

    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path = path.with_suffix(".json")
    metadata: dict[str, Any] = {}
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    expected = {
        "model": model,
        "rows": len(texts),
        "first_text": texts[0] if texts else None,
        "last_text": texts[-1] if texts else None,
    }
    valid = path.exists() and all(metadata.get(key) == value for key, value in expected.items())
    completed = int(metadata.get("completed", 0)) if valid else 0
    dimension = int(metadata.get("dimension", 0)) if valid else 0
    matrix = None
    if valid and dimension:
        matrix = np.lib.format.open_memmap(path, mode="r+", dtype=np.float16)
        if matrix.shape != (len(texts), dimension):
            matrix = None
            completed = dimension = 0
    if len(texts) == 0:
        return np.empty((0, 0), dtype=np.float32), {**expected, "completed": 0}
    if matrix is None:
        first_end = min(batch_size, len(texts))
        first = _request_embeddings(
            texts[:first_end], model=model, endpoint=endpoint, timeout=timeout
        )
        dimension = first.shape[1]
        matrix = np.lib.format.open_memmap(
            path, mode="w+", dtype=np.float16, shape=(len(texts), dimension)
        )
        matrix[:first_end] = first.astype(np.float16)
        completed = first_end
        metadata = {**expected, "dimension": dimension, "completed": completed}
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        if progress:
            progress(completed, len(texts))
    for offset in range(completed, len(texts), batch_size):
        end = min(offset + batch_size, len(texts))
        values = _request_embeddings(
            texts[offset:end], model=model, endpoint=endpoint, timeout=timeout
        )
        if values.shape[1] != dimension:
            raise ValueError("embedding dimension changed within one run")
        matrix[offset:end] = values.astype(np.float16)
        matrix.flush()
        completed = end
        metadata = {**expected, "dimension": dimension, "completed": completed}
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        if progress:
            progress(completed, len(texts))
    result = np.asarray(matrix, dtype=np.float32)
    result /= np.maximum(np.linalg.norm(result, axis=1, keepdims=True), 1e-12)
    return result, {**metadata, "cache_hit": completed == len(texts)}


def multilingual_retrieval_report(
    dataset: dict[str, Any],
    concept_ids: list[str],
    concept_embeddings: np.ndarray,
    query_embeddings: np.ndarray,
) -> dict[str, Any]:
    rows = dataset["rows"]
    rankings = rank_type_restricted(
        query_embeddings,
        [row["type"] for row in rows],
        concept_embeddings,
        concept_ids,
    )
    report: dict[str, Any] = {
        "method": "qwen3_embedding_0.6b_multilingual_dense",
        "weak_label_warning": dataset["label_status"],
        "query_instruction": QUERY_INSTRUCTION,
        "concept_nodes": len(concept_ids),
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
