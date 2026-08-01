import json
import re
from pathlib import Path

from airace.detector import detect_entities
from airace.coordinates import lf_to_crlf_offset, project_entity_to_crlf
from airace.assertions import infer_assertions
from airace.candidates import CandidateResolver
from airace.inference import _has_token_checkpoint, infer_text
from airace.hybrid import merge_specialist_entities
from airace.metrics import jaccard, score_entities, wer
from airace.llm_inference import _split_symptom
from airace.proposals import Proposal, dump_proposals, load_proposals
from airace.proposal_merge import aggregate_exact_evidence
from airace.schema import Entity
from airace.serialization import dumps_btc
from airace.silver import build_consensus
from airace.train import _trim_span
from airace.validator import validate_entities


def test_offset_preservation_with_accents():
    text = "Bệnh nhân đau ngực và khó thở."
    entities = detect_entities(text)
    validate_entities(entities, text)
    assert any(e.text == "đau ngực" for e in entities)
    assert not any(e.text in {"hở", "ho"} for e in entities)


def test_huggingface_safetensors_checkpoint_is_detected(tmp_path):
    (tmp_path / "config.json").write_text("{}")
    (tmp_path / "model.safetensors").write_bytes(b"weights")
    assert _has_token_checkpoint(tmp_path)


def test_sliding_window_fragment_is_expanded_to_raw_word():
    text = "Gãy xương hông phải"
    assert _trim_span(text, 1, len(text)) == (0, len(text))


def test_crlf_projection_reproduces_official_example_offsets():
    flat = (
        "Danh sách thuốc trước nhập viện chính xác và đầy đủ. "
        "1. amlodipine 10 mg po daily "
        "2. aspirin 81 mg po daily "
        "3. metoprolol succinate xl 50 mg po daily "
        "4. guaifenesin ml po q6h:prn điều trị ho "
        "5. nystatin oral suspension 5 ml po qid:prn điều trị đau nhức "
        "6. acetaminophen 325-650 mg po q6h:prn điều trị sốt đau "
        "7. pravastatin 40 mg po daily "
        "8. docusate sodium 100 mg po bid điều trị táo bón "
        "9. senna 8.6 mg po bid:prn điều trị táo bón "
        "10. clonazepam 0.5 mg po qam:prn điều trị lo âu "
        "11. clonazepam 1.5 mg po qhs điều trị lo âu mất ngủ"
    )
    lf_text = re.sub(r" (?=\d+\. )", " \n", flat)
    start = lf_text.index("amlodipine 10 mg po daily")
    entity = Entity(
        "amlodipine 10 mg po daily",
        "THUỐC",
        position=(start, start + 25),
    )
    projected = project_entity_to_crlf(lf_text, entity)
    assert projected.position == (58, 83)
    assert lf_to_crlf_offset(lf_text, len(lf_text)) == 554
    validate_entities([projected], lf_text, position_mode="crlf")


def test_specialist_hybrid_routes_types_and_removes_icd_candidates():
    text = "đau ngực metoprolol"
    learned = [
        Entity("đau ngực", "TRIỆU_CHỨNG", position=(0, 8)),
        Entity(
            "đau ngực",
            "CHẨN_ĐOÁN",
            candidates=["R07.9"],
            position=(0, 8),
        ),
    ]
    legacy = [
        Entity(
            "metoprolol",
            "THUỐC",
            candidates=["6918"],
            position=(9, 19),
        )
    ]
    merged, _ = merge_specialist_entities(text, learned, legacy)
    assert {(item.text, item.type) for item in merged} == {
        ("đau ngực", "TRIỆU_CHỨNG"),
        ("đau ngực", "CHẨN_ĐOÁN"),
        ("metoprolol", "THUỐC"),
    }
    diagnosis = next(item for item in merged if item.type == "CHẨN_ĐOÁN")
    assert diagnosis.candidates == []
    drug = next(item for item in merged if item.type == "THUỐC")
    assert drug.candidates == ["6918"]


def test_duplicate_occurrences_are_kept():
    text = "ho; ho; không ho."
    entities = detect_entities(text)
    assert [e.text for e in entities].count("ho") == 3
    validate_entities(entities, text)


def test_drug_span_and_candidate():
    text = "Hiện đang dùng clonazepam 0.5 mg po qam:prn."
    entities = infer_text(text)
    drug = next(e for e in entities if e.type == "THUỐC")
    assert drug.text == "clonazepam 0.5 mg po qam:prn"
    assert drug.candidates == ["197527"]


def test_drug_unit_does_not_consume_vietnamese_word():
    text = "Bệnh nhân được khí dung albuterol 2 lần."
    drug = next(e for e in infer_text(text) if e.type == "THUỐC")
    assert drug.text == "albuterol"
    assert drug.candidates == ["435"]


def test_lab_aliases_are_not_emitted_as_drugs():
    text = "Creatinine 5.7 và glucose 316, lactate 1.3."
    entities = infer_text(text)
    assert not any(e.type == "THUỐC" for e in entities)
    assert any(e.type == "TÊN_XÉT_NGHIỆM" and e.text.casefold() == "creatinine" for e in entities)
    assert any(e.type == "TÊN_XÉT_NGHIỆM" and e.text.casefold() == "glucose" for e in entities)


def test_rxnorm_typo_alias_is_top_one_only():
    text = "Đã dùng Laxis 20mg tiêm tĩnh mạch."
    drug = next(e for e in infer_text(text) if e.type == "THUỐC")
    assert drug.text == "Laxis 20mg"
    assert drug.candidates == ["1719290"]


def test_bare_ingredient_uses_rxnorm_ingredient_not_arbitrary_product():
    # RxNorm IN concepts from the bundled CPC catalog.  This guards against
    # treating the first lexicographic product in the broad product index as
    # an ingredient match (which may be a multi-ingredient medicine).
    for text, expected in [
        ("acetaminophen", "161"),
        ("aspirin", "1191"),
        ("metoprolol", "6918"),
    ]:
        drug = next(e for e in infer_text(text) if e.type == "THUỐC")
        assert drug.candidates == [expected]


def test_explicit_iv_requires_a_route_and_strength_consistent_product():
    # The organizer sample overwhelmingly uses SCD codes when it supplies a
    # strength/form.  Route is an explicit part of the BTC drug span, so an IV
    # mention must not silently fall back to an oral tablet or bare ingredient.
    cases = [
        ("iv lasix 40 mg once", ["1719291"]),
        ("levofloxacin 750mg iv", ["1665515"]),
        ("bumetanide 2mg iv", []),  # no matching injectable SCD package
    ]
    for text, expected in cases:
        drug = next(e for e in infer_text(text) if e.type == "THUỐC")
        assert drug.candidates == expected


def test_recall_section_rule_ignores_metadata_labels():
    text = "Triệu chứng hiện tại\n- Vị trí: ngực\n- Yếu tố làm nặng thêm: vận động"
    entities = detect_entities(text, profile="recall")
    assert not any(e.text in {"Vị trí", "Yếu tố làm nặng thêm"} for e in entities)


def test_metrics_empty_sets_and_extra_candidate():
    assert jaccard([], []) == 1.0
    assert jaccard([], ["K21.9"]) == 0.0
    assert wer("đau ngực", "đau ngực") == 0.0
    gold = [Entity("GERD", "CHẨN_ĐOÁN", candidates=["K21.9"], position=(0, 4))]
    pred = [Entity("GERD", "CHẨN_ĐOÁN", candidates=["K21.9", "K21.0"], position=(0, 4))]
    score = score_entities(gold, pred)
    assert score["candidates_score"] == 0.5


def test_official_style_output_is_serializable():
    text = "Bệnh nhân có tiền sử GERD."
    entities = infer_text(text)
    payload = json.loads(json.dumps([e.to_dict() for e in entities], ensure_ascii=False))
    assert isinstance(payload, list)
    validate_entities([Entity.from_dict(v) for v in payload], text)


def test_btc_serializer_keeps_short_arrays_inline():
    values = [
        {
            "text": "atenolol",
            "type": "THUỐC",
            "candidates": ["1202"],
            "assertions": ["isHistorical"],
            "position": [10, 18],
        }
    ]
    serialized = dumps_btc(values)
    assert '"candidates": ["1202"]' in serialized
    assert '"assertions": ["isHistorical"]' in serialized
    assert '"position": [10, 18]' in serialized
    assert json.loads(serialized) == values


def test_proposal_sidecar_preserves_confidence_and_source(tmp_path):
    entity = Entity(
        text="khó thở",
        type="TRIỆU_CHỨNG",
        position=(0, 6),
        confidence=0.913,
        source="model-a",
    )
    path = tmp_path / "1.json"
    dump_proposals([Proposal.from_entity(entity)], path)

    restored = load_proposals(path)[0]
    assert restored.confidence == 0.913
    assert restored.source == "model-a"
    assert restored.to_entity().to_dict() == entity.to_dict()


def test_candidate_resolver_abstains_when_lexicon_has_no_catalog_alias():
    resolver = CandidateResolver()
    for text in ("NSAID", "doxycyclinebactrim", "Insulin"):
        entity = Entity(text=text, type="THUỐC", position=(0, len(text)))
        resolver.resolve(entity, text)
        assert isinstance(entity.candidates, list)


def test_proposal_evidence_deduplicates_each_source_and_tracks_baseline():
    first = Proposal(
        text="đau ngực",
        type="TRIỆU_CHỨNG",
        position=(0, 8),
        confidence=0.8,
        source="model-a",
    )
    duplicate = Proposal(
        text="đau ngực",
        type="TRIỆU_CHỨNG",
        position=(0, 8),
        confidence=0.9,
        source="model-a",
    )
    second = Proposal(
        text="đau ngực",
        type="TRIỆU_CHỨNG",
        position=(0, 8),
        confidence=0.7,
        source="model-b",
    )
    baseline = [Entity("đau ngực", "TRIỆU_CHỨNG", position=(0, 8))]

    evidence = aggregate_exact_evidence(
        [[first, duplicate], [second]],
        baseline,
    )[0]
    assert evidence.sources == ("model-a", "model-b")
    assert evidence.confidences == (0.9, 0.7)
    assert evidence.source_count == 2
    assert evidence.baseline_exact
    assert evidence.baseline_overlap_same_type


def test_consensus_uses_teacher_to_tighten_verbose_qwen_span():
    text = "Bệnh nhân cảm thấy đau ngực dữ dội."
    qwen = [
        Entity(
            "cảm thấy đau ngực dữ dội",
            "TRIỆU_CHỨNG",
            position=(10, 34),
            confidence=0.86,
            source="qwen3",
        )
    ]
    teacher = [
        Entity(
            "đau ngực",
            "TRIỆU_CHỨNG",
            position=(19, 27),
            confidence=0.98,
            source="bami_teacher",
        )
    ]
    entities, sources = build_consensus(text, qwen, [], teacher)
    assert [(entity.text, entity.type) for entity in entities] == [
        ("đau ngực", "TRIỆU_CHỨNG")
    ]
    assert sources["teacher+qwen"] == 1


def test_official_compound_symptom_boundary():
    text = "acetaminophen 325-650 mg po q6h:prn điều trị sốt đau"
    entities = infer_text(text, profile="baseline")
    assert any(
        entity.text == "sốt đau" and entity.type == "TRIỆU_CHỨNG"
        for entity in entities
    )


def test_split_symptom_does_not_extract_ho_inside_thoang():
    text = "buồn nôn thoáng qua và đau bụng"
    entity = Entity(text, "TRIỆU_CHỨNG", position=(0, len(text)))
    split = _split_symptom(entity, text)
    assert [(item.text, item.type) for item in split] == [
        ("buồn nôn", "TRIỆU_CHỨNG"),
        ("đau bụng", "TRIỆU_CHỨNG"),
    ]


def test_negation_scope_and_non_negating_qualifiers():
    text = (
        "Chẩn đoán: xuất huyết nội sọ không do chấn thương, không đặc hiệu. "
        "Hiện không đau ngực nhưng có khó thở."
    )
    diagnosis_text = "xuất huyết nội sọ không do chấn thương, không đặc hiệu"
    diagnosis_start = text.index(diagnosis_text)
    diagnosis = Entity(
        diagnosis_text,
        "CHẨN_ĐOÁN",
        position=(diagnosis_start, diagnosis_start + len(diagnosis_text)),
    )
    pain_start = text.index("đau ngực")
    pain = Entity(
        "đau ngực",
        "TRIỆU_CHỨNG",
        position=(pain_start, pain_start + len("đau ngực")),
    )
    dyspnea_start = text.index("khó thở")
    dyspnea = Entity(
        "khó thở", "TRIỆU_CHỨNG", position=(dyspnea_start, dyspnea_start + 7)
    )
    assert "isNegated" not in infer_assertions(diagnosis, text)
    assert "isNegated" in infer_assertions(pain, text)
    assert "isNegated" not in infer_assertions(dyspnea, text)


def test_assertions_are_empty_for_test_entities():
    text = "Kết quả: chụp CT không phát hiện bất thường"
    start = text.index("chụp CT")
    entity = Entity(
        "chụp CT",
        "TÊN_XÉT_NGHIỆM",
        position=(start, start + len("chụp CT")),
    )
    assert infer_assertions(entity, text) == []


def test_family_reporter_does_not_make_patient_symptom_family_history():
    text = "Người nhà nhận thấy bệnh nhân mất định hướng"
    start = text.index("mất định hướng")
    entity = Entity(
        "mất định hướng",
        "TRIỆU_CHỨNG",
        position=(start, start + len("mất định hướng")),
    )
    assert "isFamily" not in infer_assertions(entity, text)


def test_relative_subject_is_family_history():
    text = "Mẹ đã tử vong"
    start = text.index("tử vong")
    entity = Entity(
        "tử vong",
        "TRIỆU_CHỨNG",
        position=(start, start + len("tử vong")),
    )
    assert "isFamily" in infer_assertions(entity, text)


def test_numbered_medical_history_marks_symptom_historical():
    text = "1. Tiền sử bệnh\n- ngất xỉu\n\n2. Bệnh sử hiện tại\n- khó thở"
    start = text.index("ngất xỉu")
    entity = Entity(
        "ngất xỉu",
        "TRIỆU_CHỨNG",
        position=(start, start + len("ngất xỉu")),
    )
    assert "isHistorical" in infer_assertions(entity, text)
