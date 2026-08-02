from airace.independent_agreement import key


def test_agreement_key_is_exact_span_type_and_record():
    row = {"position": [2, 7], "type": "TRIỆU_CHỨNG", "record": 4}
    assert key(row) == (2, 7, "TRIỆU_CHỨNG", 4)
