from airace.section_expert_recall import unsupported_row_allowed


def row(text: str, kind: str) -> dict:
    return {"text": text, "type": kind}


def test_type_router_accepts_clinical_and_numeric_result() -> None:
    assert unsupported_row_allowed(row("đau ngực", "TRIỆU_CHỨNG"))
    assert unsupported_row_allowed(row("Huyết áp 139/68 mmHg", "KẾT_QUẢ_XÉT_NGHIỆM"))


def test_type_router_rejects_patient_and_uncoded_drug() -> None:
    assert not unsupported_row_allowed(row("hệ thần kinh", "THÔNG_TIN_BỆNH_NHÂN"))
    assert not unsupported_row_allowed(row("truyền tĩnh mạch", "THUỐC"))
    assert not unsupported_row_allowed(row("bình thường", "KẾT_QUẢ_XÉT_NGHIỆM"))
