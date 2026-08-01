from __future__ import annotations

from airace.schema import Entity


OFFICIAL_TEXT = (
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


def official_gold() -> list[Entity]:
    specs = [
        ("amlodipine 10 mg po daily", "THUỐC", ["308135"], ["isHistorical"]),
        ("aspirin 81 mg po daily", "THUỐC", ["243670"], ["isHistorical"]),
        ("metoprolol succinate xl 50 mg po daily", "THUỐC", ["866436"], ["isHistorical"]),
        ("guaifenesin ml po q6h:prn", "THUỐC", ["392085"], ["isHistorical"]),
        ("ho", "TRIỆU_CHỨNG", None, []),
        ("nystatin oral suspension 5 ml po qid:prn", "THUỐC", ["7597"], ["isHistorical"]),
        ("đau nhức", "TRIỆU_CHỨNG", None, []),
        ("acetaminophen 325-650 mg po q6h:prn", "THUỐC", ["313782"], ["isHistorical"]),
        ("sốt đau", "TRIỆU_CHỨNG", None, []),
        ("pravastatin 40 mg po daily", "THUỐC", ["904475"], ["isHistorical"]),
        ("docusate sodium 100 mg po bid", "THUỐC", ["1099279"], ["isHistorical"]),
        ("táo bón", "TRIỆU_CHỨNG", None, []),
        ("senna 8.6 mg po bid:prn", "THUỐC", ["312935"], ["isHistorical"]),
        ("táo bón", "TRIỆU_CHỨNG", None, []),
        ("clonazepam 0.5 mg po qam:prn", "THUỐC", ["197527"], ["isHistorical"]),
        ("lo âu", "TRIỆU_CHỨNG", None, []),
        ("clonazepam 1.5 mg po qhs", "THUỐC", ["197528"], ["isHistorical"]),
        ("lo âu", "TRIỆU_CHỨNG", None, []),
        ("mất ngủ", "TRIỆU_CHỨNG", None, []),
    ]
    cursor = 0
    entities: list[Entity] = []
    for text, kind, candidates, assertions in specs:
        start = OFFICIAL_TEXT.index(text, cursor)
        end = start + len(text)
        cursor = end
        entities.append(
            Entity(
                text=text,
                type=kind,
                candidates=candidates,
                assertions=assertions,
                position=(start, end),
            )
        )
    return entities
