from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch
from torch import Tensor, nn
from torch.nn import functional as F


def masked_mean(last_hidden_state: Tensor, attention_mask: Tensor) -> Tensor:
    mask = attention_mask.unsqueeze(-1).to(last_hidden_state.dtype)
    denominator = mask.sum(dim=1).clamp_min(1.0)
    return (last_hidden_state * mask).sum(dim=1) / denominator


class RelationGraphAdapter(nn.Module):
    """Small relation-aware graph layer without a torch-geometric dependency."""

    def __init__(self, hidden_size: int, relation_count: int, dropout: float = 0.1):
        super().__init__()
        self.self_projection = nn.Linear(hidden_size, hidden_size)
        self.relation_projection = nn.Parameter(
            torch.empty(relation_count, hidden_size, hidden_size)
        )
        self.norm = nn.LayerNorm(hidden_size)
        self.dropout = nn.Dropout(dropout)
        nn.init.xavier_uniform_(self.relation_projection)

    def forward(self, nodes: Tensor, edge_index: Tensor, relation_ids: Tensor) -> Tensor:
        if edge_index.numel() == 0:
            return self.norm(F.gelu(self.self_projection(nodes)))
        source, target = edge_index
        weights = self.relation_projection[relation_ids]
        messages = torch.bmm(nodes[source].unsqueeze(1), weights).squeeze(1)
        aggregate = torch.zeros_like(nodes)
        aggregate.index_add_(0, target, messages)
        degree = torch.zeros(nodes.shape[0], device=nodes.device, dtype=nodes.dtype)
        degree.index_add_(0, target, torch.ones_like(target, dtype=nodes.dtype))
        aggregate = aggregate / degree.clamp_min(1.0).unsqueeze(-1)
        return self.norm(
            nodes + self.dropout(F.gelu(self.self_projection(nodes) + aggregate))
        )


class OntologyDualEncoder(nn.Module):
    """Customized mention/concept encoder with separate projection spaces."""

    def __init__(
        self,
        backbone: nn.Module,
        hidden_size: int,
        embedding_size: int = 256,
        relation_count: int = 0,
        temperature: float = 0.07,
    ):
        super().__init__()
        self.backbone = backbone
        self.mention_projection = nn.Sequential(
            nn.Linear(hidden_size, embedding_size),
            nn.GELU(),
            nn.LayerNorm(embedding_size),
        )
        self.concept_projection = nn.Sequential(
            nn.Linear(hidden_size, embedding_size),
            nn.GELU(),
            nn.LayerNorm(embedding_size),
        )
        self.graph_adapter = (
            RelationGraphAdapter(embedding_size, relation_count)
            if relation_count
            else None
        )
        self.temperature = temperature

    def _encode(self, batch: dict[str, Tensor], projection: nn.Module) -> Tensor:
        output = self.backbone(**batch)
        pooled = masked_mean(output.last_hidden_state, batch["attention_mask"])
        return F.normalize(projection(pooled), dim=-1)

    def encode_mentions(self, batch: dict[str, Tensor]) -> Tensor:
        return self._encode(batch, self.mention_projection)

    def encode_concepts(self, batch: dict[str, Tensor]) -> Tensor:
        return self._encode(batch, self.concept_projection)

    def adapt_graph(
        self,
        concept_embeddings: Tensor,
        edge_index: Tensor,
        relation_ids: Tensor,
    ) -> Tensor:
        if self.graph_adapter is None:
            return concept_embeddings
        return F.normalize(
            self.graph_adapter(concept_embeddings, edge_index, relation_ids), dim=-1
        )

    def contrastive_loss(
        self,
        mention_embeddings: Tensor,
        concept_embeddings: Tensor,
        positive_mask: Tensor | None = None,
    ) -> Tensor:
        logits = mention_embeddings @ concept_embeddings.T / self.temperature
        if positive_mask is None:
            labels = torch.arange(logits.shape[0], device=logits.device)
            return (F.cross_entropy(logits, labels) + F.cross_entropy(logits.T, labels)) / 2
        log_prob = logits.log_softmax(dim=-1)
        positive = positive_mask.to(log_prob.dtype)
        loss = -(torch.logsumexp(log_prob.masked_fill(positive == 0, -torch.inf), dim=-1))
        return loss.mean()

    @staticmethod
    def graph_alignment_loss(
        embeddings: Tensor,
        edge_index: Tensor,
        negative_index: Tensor,
        margin: float = 0.2,
    ) -> Tensor:
        source, positive = edge_index
        positive_similarity = F.cosine_similarity(embeddings[source], embeddings[positive])
        negative_similarity = F.cosine_similarity(embeddings[source], embeddings[negative_index])
        return F.relu(margin - positive_similarity + negative_similarity).mean()


@dataclass(frozen=True)
class ClassifierOutput:
    keep_logits: Tensor
    type_logits: Tensor
    compatibility_logits: Tensor
    assertion_logits: Tensor


class ContextOntologyClassifier(nn.Module):
    """Pairwise context/concept classifier used after top-k retrieval."""

    def __init__(
        self,
        backbone: nn.Module,
        hidden_size: int,
        numeric_feature_count: int,
        entity_type_count: int = 6,
        assertion_count: int = 3,
    ):
        super().__init__()
        self.backbone = backbone
        fused_size = hidden_size + numeric_feature_count
        self.fusion = nn.Sequential(
            nn.Linear(fused_size, hidden_size),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.LayerNorm(hidden_size),
        )
        self.keep_head = nn.Linear(hidden_size, 2)
        self.type_head = nn.Linear(hidden_size, entity_type_count)
        self.compatibility_head = nn.Linear(hidden_size, 1)
        self.assertion_head = nn.Linear(hidden_size, assertion_count)

    def forward(self, batch: dict[str, Tensor], numeric_features: Tensor) -> ClassifierOutput:
        output = self.backbone(**batch)
        pooled = masked_mean(output.last_hidden_state, batch["attention_mask"])
        fused = self.fusion(torch.cat((pooled, numeric_features), dim=-1))
        return ClassifierOutput(
            keep_logits=self.keep_head(fused),
            type_logits=self.type_head(fused),
            compatibility_logits=self.compatibility_head(fused).squeeze(-1),
            assertion_logits=self.assertion_head(fused),
        )


def multitask_loss(
    output: ClassifierOutput,
    labels: dict[str, Tensor],
    weights: dict[str, float] | None = None,
) -> tuple[Tensor, dict[str, Tensor]]:
    weights = weights or {}
    parts = {
        "keep": F.cross_entropy(output.keep_logits, labels["keep"]),
        "type": F.cross_entropy(output.type_logits, labels["type"]),
        "compatibility": F.binary_cross_entropy_with_logits(
            output.compatibility_logits, labels["compatibility"].float()
        ),
        "assertions": F.binary_cross_entropy_with_logits(
            output.assertion_logits, labels["assertions"].float()
        ),
    }
    total = sum(weights.get(name, 1.0) * value for name, value in parts.items())
    return total, parts

