import numpy as np
import torch

from airace.ontology_alignment import AlignmentModel, _multi_positive_loss


def test_multi_positive_loss_accepts_either_positive() -> None:
    logits = torch.tensor([[4.0, 3.0, -1.0], [-1.0, 4.0, 0.0]])
    mask = torch.tensor([[True, True, False], [False, True, False]])
    loss = _multi_positive_loss(logits, mask)
    assert torch.isfinite(loss)
    assert loss.item() < 0.1


def test_alignment_projection_normalizes_embeddings() -> None:
    torch.manual_seed(2)
    model = AlignmentModel(4, 8, 3)
    mention = model.mention_projection(torch.from_numpy(np.ones((2, 4), dtype=np.float32)))
    concept = model.concept_projection(torch.from_numpy(np.ones((2, 8), dtype=np.float32)))
    assert torch.allclose(mention.norm(dim=-1), torch.ones(2), atol=1e-5)
    assert torch.allclose(concept.norm(dim=-1), torch.ones(2), atol=1e-5)

