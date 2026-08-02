from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from .normalize import normalize_key
from .ontology_graph import OntologyGraph


def _context(raw_text: str, start: int, end: int, width: int = 120) -> str:
    return (
        raw_text[max(0, start - width):start]
        + "⟦"
        + raw_text[start:end]
        + "⟧"
        + raw_text[end:min(len(raw_text), end + width)]
    )


def build_pseudo_link_dataset(
    input_dir: str | Path,
    source_dir: str | Path,
    graph: OntologyGraph,
) -> dict[str, Any]:
    """Build provenance-marked weak mention/concept pairs from a frozen output.

    Identical normalized aliases are assigned to the same fold so a surface
    form cannot appear on both sides of a future training/evaluation split.
    This is weak-label infrastructure, not organizer ground truth.
    """

    inputs, source = Path(input_dir), Path(source_dir)
    grouped: dict[tuple[str, str, tuple[str, ...]], dict[str, Any]] = {}
    skipped: dict[str, int] = defaultdict(int)
    for path in sorted(source.glob("*.json"), key=lambda item: int(item.stem)):
        raw_text = (inputs / f"{path.stem}.txt").read_text(encoding="utf-8")
        for entity in json.loads(path.read_text(encoding="utf-8")):
            kind = entity["type"]
            if kind not in {"CHẨN_ĐOÁN", "THUỐC"}:
                continue
            prefix = "ICD:" if kind == "CHẨN_ĐOÁN" else "RX:"
            identifiers = tuple(
                sorted(
                    {
                        prefix + str(code)
                        for code in entity.get("candidates", [])
                        if prefix + str(code) in graph.nodes
                    }
                )
            )
            if not identifiers:
                skipped[f"no_graph_candidate:{kind}"] += 1
                continue
            start, end = entity["position"]
            if not (0 <= start < end <= len(raw_text)) or raw_text[start:end] != entity["text"]:
                skipped["invalid_offset"] += 1
                continue
            alias = normalize_key(entity["text"])
            key = alias, kind, identifiers
            row = grouped.setdefault(
                key,
                {
                    "mention": entity["text"],
                    "normalized_mention": alias,
                    "type": kind,
                    "gold_concepts": list(identifiers),
                    "contexts": [],
                    "records": [],
                    "uses": 0,
                    "provenance": "H23_WEAK_LABEL",
                },
            )
            row["uses"] += 1
            if path.stem not in row["records"]:
                row["records"].append(path.stem)
            if len(row["contexts"]) < 3:
                row["contexts"].append(_context(raw_text, start, end))
    rows = sorted(
        grouped.values(),
        key=lambda row: (row["type"], row["normalized_mention"], row["gold_concepts"]),
    )
    fold_counts: dict[str, int] = defaultdict(int)
    for identifier, row in enumerate(rows):
        digest = hashlib.sha256(row["normalized_mention"].encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % 10
        fold = "test" if bucket == 0 else "dev" if bucket == 1 else "train"
        row["id"] = identifier
        row["fold"] = fold
        row["records"].sort(key=int)
        fold_counts[fold] += 1
    payload = {
        "label_status": "weak_pseudo_labels_not_organizer_ground_truth",
        "source": str(source),
        "rows": rows,
        "row_count": len(rows),
        "fold_counts": dict(sorted(fold_counts.items())),
        "skipped": dict(sorted(skipped.items())),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["dataset_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def write_dataset(dataset: dict[str, Any], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def lexical_retrieval_baseline(
    graph: OntologyGraph,
    dataset: dict[str, Any],
    *,
    ngram_range: tuple[int, int] = (2, 5),
    batch_size: int = 64,
) -> dict[str, Any]:
    alias_texts: list[str] = []
    alias_nodes: list[str] = []
    for identifier in sorted(graph.nodes):
        node = graph.nodes[identifier]
        for alias in node.aliases or (node.canonical,):
            alias_texts.append(alias)
            alias_nodes.append(identifier)
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=ngram_range,
        lowercase=True,
        dtype=np.float32,
        norm="l2",
    )
    concept_matrix = vectorizer.fit_transform(alias_texts)
    eligible_indices = {
        "CHẨN_ĐOÁN": np.asarray(
            [index for index, node in enumerate(alias_nodes) if node.startswith("ICD:")],
            dtype=np.int64,
        ),
        "THUỐC": np.asarray(
            [index for index, node in enumerate(alias_nodes) if node.startswith("RX:")],
            dtype=np.int64,
        ),
    }
    rows = dataset["rows"]
    query_matrix = vectorizer.transform([row["mention"] for row in rows])
    hits = {1: 0, 5: 0, 10: 0}
    type_hits: dict[str, dict[int, int]] = defaultdict(lambda: {1: 0, 5: 0, 10: 0})
    type_total: dict[str, int] = defaultdict(int)
    predictions: list[dict[str, Any]] = []
    for offset in range(0, len(rows), batch_size):
        scores = query_matrix[offset:offset + batch_size] @ concept_matrix.T
        for local, row in enumerate(rows[offset:offset + batch_size]):
            dense = scores.getrow(local).toarray().ravel()
            pool = eligible_indices[row["type"]]
            pool_scores = dense[pool]
            # Retrieve more aliases than nodes, then deterministically dedupe.
            count = min(100, len(pool_scores))
            selected = np.argpartition(pool_scores, -count)[-count:]
            indices = pool[selected]
            indices = sorted(indices, key=lambda index: (-float(dense[index]), alias_nodes[index]))
            ranked: list[str] = []
            for index in indices:
                node = alias_nodes[index]
                if node not in ranked:
                    ranked.append(node)
                if len(ranked) == 10:
                    break
            gold = set(row["gold_concepts"])
            kind = row["type"]
            type_total[kind] += 1
            for k in hits:
                matched = bool(gold.intersection(ranked[:k]))
                hits[k] += int(matched)
                type_hits[kind][k] += int(matched)
            predictions.append(
                {
                    "id": row["id"],
                    "gold": row["gold_concepts"],
                    "top10": ranked,
                }
            )
    total = len(rows) or 1
    return {
        "method": "char_wb_tfidf",
        "ngram_range": list(ngram_range),
        "queries": len(rows),
        "concept_nodes": len(graph.nodes),
        "concept_aliases": len(alias_texts),
        "recall": {f"@{k}": hits[k] / total for k in sorted(hits)},
        "recall_by_type": {
            kind: {f"@{k}": values[k] / type_total[kind] for k in sorted(values)}
            for kind, values in sorted(type_hits.items())
        },
        "predictions": predictions,
    }
