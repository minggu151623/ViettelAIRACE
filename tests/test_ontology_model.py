from types import SimpleNamespace

import torch
from torch import nn

from airace.ontology_model import (
    ContextOntologyClassifier,
    OntologyDualEncoder,
    RelationGraphAdapter,
    masked_mean,
    multitask_loss,
)


class DummyBackbone(nn.Module):
    def __init__(self, hidden_size: int = 8):
        super().__init__()
        self.embedding = nn.Embedding(32, hidden_size)

    def forward(self, input_ids, attention_mask):
        return SimpleNamespace(last_hidden_state=self.embedding(input_ids))


def test_masked_mean_ignores_padding() -> None:
    values = torch.tensor([[[1.0], [3.0], [100.0]]])
    mask = torch.tensor([[1, 1, 0]])
    assert masked_mean(values, mask).item() == 2.0


def test_relation_graph_adapter_changes_connected_target() -> None:
    torch.manual_seed(7)
    layer = RelationGraphAdapter(4, relation_count=2, dropout=0.0)
    nodes = torch.eye(4)
    result = layer(nodes, torch.tensor([[0], [1]]), torch.tensor([0]))
    assert result.shape == nodes.shape
    assert not torch.equal(result[1], nodes[1])


def test_dual_encoder_and_multitask_classifier_shapes() -> None:
    batch = {
        "input_ids": torch.tensor([[1, 2, 0], [3, 4, 5]]),
        "attention_mask": torch.tensor([[1, 1, 0], [1, 1, 1]]),
    }
    encoder = OntologyDualEncoder(DummyBackbone(), hidden_size=8, embedding_size=4)
    mentions = encoder.encode_mentions(batch)
    concepts = encoder.encode_concepts(batch)
    assert mentions.shape == concepts.shape == (2, 4)
    assert torch.isfinite(encoder.contrastive_loss(mentions, concepts))

    classifier = ContextOntologyClassifier(
        DummyBackbone(), hidden_size=8, numeric_feature_count=3
    )
    output = classifier(batch, torch.zeros(2, 3))
    total, parts = multitask_loss(
        output,
        {
            "keep": torch.tensor([1, 0]),
            "type": torch.tensor([0, 2]),
            "compatibility": torch.tensor([1, 0]),
            "assertions": torch.tensor([[1, 0, 0], [0, 1, 1]]),
        },
    )
    assert torch.isfinite(total)
    assert set(parts) == {"keep", "type", "compatibility", "assertions"}

