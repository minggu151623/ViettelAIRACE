import numpy as np

from airace.all_in_ontology_linker import _batch_rank, normalize_mention


def test_normalize_mention_is_unicode_and_case_stable() -> None:
    assert normalize_mention("  BỆNH   Dại ") == "bệnh dại"


def test_batch_rank_respects_entity_type() -> None:
    concept_ids = ["ICD:A00", "ICD:B00", "RX:1", "RX:2"]
    concepts = np.asarray([[1, 0], [0, 1], [1, 0], [0, 1]], dtype=np.float32)
    queries = np.asarray([[1, 0], [0, 1]], dtype=np.float32)
    ranked = _batch_rank(queries, ["CHẨN_ĐOÁN", "THUỐC"], concepts, concept_ids, top_k=1)
    assert ranked == [["ICD:A00"], ["RX:2"]]
