from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from .ontology_dense import _metric_block, choose_device
from .ontology_graph import OntologyGraph


RERANK_INSTRUCTION = (
    "Given a Vietnamese clinical mention in context, determine whether the English "
    "ontology concept is the correct normalization. A diagnosis must match ICD-10 "
    "meaning and specificity; a drug must match the RxNorm ingredient or product."
)
PREFIX = (
    '<|im_start|>system\nJudge whether the Document meets the requirements based on '
    'the Query and the Instruct provided. Note that the answer can only be "yes" or '
    '"no".<|im_end|>\n<|im_start|>user\n'
)
SUFFIX = '<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'


def format_rerank_query(row: dict[str, Any]) -> str:
    context = row.get("contexts", [""])[0] if row.get("contexts") else ""
    return f"Entity type: {row['type']}\nMention: {row['mention']}\nContext: {context}"


def _relation_index(graph: OntologyGraph) -> dict[str, list[tuple[str, str]]]:
    index: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for edge in graph.edges:
        index[edge.source].append((edge.relation, edge.target))
    priority = {
        "icd_parent": 0,
        "rx_has_ingredient": 1,
        "rx_has_precise_ingredient": 2,
        "rx_has_dose_form": 3,
        "rx_isa": 4,
    }
    for identifier, values in index.items():
        values.sort(key=lambda item: (priority.get(item[0], 20), item[0], item[1]))
    return index


def format_concept_document(
    graph: OntologyGraph,
    identifier: str,
    *,
    include_graph: bool,
    relation_index: dict[str, list[tuple[str, str]]] | None = None,
    max_relations: int = 8,
) -> str:
    node = graph.nodes[identifier]
    ontology = "WHO ICD-10 2019" if identifier.startswith("ICD:") else "RxNorm CPC"
    values = [f"Ontology: {ontology}", f"Code: {identifier.split(':', 1)[1]}", f"Title: {node.canonical}"]
    if include_graph:
        relation_index = relation_index or _relation_index(graph)
        related = []
        for relation, target in relation_index.get(identifier, [])[:max_relations]:
            target_node = graph.nodes.get(target)
            if target_node is not None:
                related.append(f"{relation} -> {target_node.canonical} [{target}]")
        if related:
            values.append("Direct ontology relations: " + "; ".join(related))
    return "\n".join(values)


def format_instruction(query: str, document: str) -> str:
    return f"<Instruct>: {RERANK_INSTRUCTION}\n<Query>: {query}\n<Document>: {document}"


class QwenOntologyReranker:
    def __init__(
        self,
        model_path: str | Path,
        *,
        device: str = "auto",
        max_length: int = 512,
    ):
        self.device = choose_device(device)
        self.max_length = max_length
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(model_path), local_files_only=True, padding_side="left"
        )
        dtype = torch.float16 if self.device.type in {"mps", "cuda"} else torch.float32
        self.model = AutoModelForCausalLM.from_pretrained(
            str(model_path), local_files_only=True, torch_dtype=dtype
        ).eval().to(self.device)
        self.no_id = self.tokenizer.convert_tokens_to_ids("no")
        self.yes_id = self.tokenizer.convert_tokens_to_ids("yes")
        self.prefix_tokens = self.tokenizer.encode(PREFIX, add_special_tokens=False)
        self.suffix_tokens = self.tokenizer.encode(SUFFIX, add_special_tokens=False)

    def _inputs(self, pairs: list[tuple[str, str]]) -> dict[str, torch.Tensor]:
        texts = [format_instruction(query, document) for query, document in pairs]
        body_limit = self.max_length - len(self.prefix_tokens) - len(self.suffix_tokens)
        tokenized = self.tokenizer(
            texts,
            padding=False,
            truncation=True,
            max_length=body_limit,
            return_attention_mask=False,
        )
        tokenized["input_ids"] = [
            self.prefix_tokens + value + self.suffix_tokens for value in tokenized["input_ids"]
        ]
        padded = self.tokenizer.pad(tokenized, padding=True, return_tensors="pt")
        return {key: value.to(self.device) for key, value in padded.items()}

    @torch.inference_mode()
    def score(self, pairs: Iterable[tuple[str, str]], *, batch_size: int = 32) -> list[float]:
        values = list(pairs)
        scores: list[float] = []
        for offset in range(0, len(values), batch_size):
            inputs = self._inputs(values[offset:offset + batch_size])
            # Compute only the final-token vocabulary logits. This is exactly
            # equivalent to model(...).logits[:, -1, :] but avoids allocating
            # sequence_length x vocabulary for every pair.
            hidden = self.model.model(**inputs, use_cache=False).last_hidden_state[:, -1, :]
            logits = self.model.lm_head(hidden)[:, [self.no_id, self.yes_id]].float()
            scores.extend(torch.softmax(logits, dim=-1)[:, 1].cpu().tolist())
        return scores


def rerank_fold(
    graph: OntologyGraph,
    dataset: dict[str, Any],
    router_report: dict[str, Any],
    scorer: QwenOntologyReranker,
    *,
    fold: str,
    include_graph: bool,
    batch_size: int = 32,
) -> dict[str, Any]:
    rows_by_id = {row["id"]: row for row in dataset["rows"]}
    selected = [value for value in router_report["predictions"] if value["fold"] == fold]
    relation_index = _relation_index(graph) if include_graph else None
    pairs: list[tuple[str, str]] = []
    ownership: list[tuple[int, str, int]] = []
    for prediction in selected:
        row = rows_by_id[prediction["id"]]
        query = format_rerank_query(row)
        for original_rank, identifier in enumerate(prediction["top10"]):
            document = format_concept_document(
                graph,
                identifier,
                include_graph=include_graph,
                relation_index=relation_index,
            )
            pairs.append((query, document))
            ownership.append((row["id"], identifier, original_rank))
    pair_scores = scorer.score(pairs, batch_size=batch_size)
    grouped: dict[int, list[tuple[float, int, str]]] = defaultdict(list)
    for (row_id, identifier, original_rank), score in zip(ownership, pair_scores):
        grouped[row_id].append((score, original_rank, identifier))
    rankings: list[list[str]] = []
    rows: list[dict[str, Any]] = []
    predictions: list[dict[str, Any]] = []
    for prediction in selected:
        row = rows_by_id[prediction["id"]]
        ordered = sorted(grouped[row["id"]], key=lambda item: (-item[0], item[1], item[2]))
        ranking = [identifier for _, _, identifier in ordered]
        rankings.append(ranking)
        rows.append(row)
        predictions.append(
            {
                "id": row["id"],
                "fold": fold,
                "gold": row["gold_concepts"],
                "top10": ranking,
                "scores": [score for score, _, _ in ordered],
            }
        )
    return {
        "fold": fold,
        "variant": "text_plus_graph" if include_graph else "text_only",
        "metrics": _metric_block(rows, rankings),
        "predictions": predictions,
        "pairs_scored": len(pairs),
    }


def save_reranker_report(report: dict[str, Any], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
