from airace.additive_consensus_rescue import select_disjoint_additions


def _entity(text, kind, start, end):
    return {"text": text, "type": kind, "assertions": [], "position": [start, end]}


def test_selects_only_disjoint_target_type_additions():
    baseline = [_entity("đau đầu", "TRIỆU_CHỨNG", 10, 17)]
    challenger = [
        _entity("đau đầu", "TRIỆU_CHỨNG", 10, 17),
        _entity("đau đầu dữ dội", "TRIỆU_CHỨNG", 10, 24),
        _entity("sốt", "TRIỆU_CHỨNG", 30, 33),
        _entity("CRP", "TÊN_XÉT_NGHIỆM", 40, 43),
    ]
    assert select_disjoint_additions(baseline, challenger) == [challenger[2]]
