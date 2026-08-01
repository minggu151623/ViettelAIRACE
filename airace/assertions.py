from __future__ import annotations

import re

from .normalize import enclosing_sentence
from .schema import Entity


HISTORICAL_CUES = (
    "tiền sử",
    "trước khi nhập viện",
    "trước nhập viện",
    "đã từng",
    "đã điều trị trước đây",
    "lịch sử sử dụng",
    "các bệnh lý mạn tính",
    "các bệnh lý mãn tính",
    "các bệnh đã điều trị",
)
FAMILY_CUES = ("bố bệnh nhân", "mẹ bệnh nhân", "cha bệnh nhân", "mẹ", "bố", "gia đình", "người nhà")
NEGATION_CUES = (
    "không",
    "không có",
    "chưa",
    "chưa ghi nhận",
    "không ghi nhận",
    "âm tính",
    "không còn",
    "không bị",
    "không mắc",
)
_NEGATION_RE = re.compile(
    r"(?:^|[\s,:;(\-])(?:không(?:\s+(?:có|còn|bị|mắc|ghi\s+nhận))?|"
    r"chưa(?:\s+ghi\s+nhận)?|phủ\s+nhận|âm\s+tính)\s+$",
    re.IGNORECASE,
)
_NEGATION_BREAK = re.compile(
    r"(?:\b(?:nhưng|tuy\s+nhiên|song|mặc\s+dù)\b|[.;])",
    re.IGNORECASE,
)
_NON_NEGATING_QUALIFIER = re.compile(
    r"\bkhông\s+(?:xác\s+định|đặc\s+hiệu|do|biệt\s+định)\b",
    re.IGNORECASE,
)
_ASSERTION_ENTITY_TYPES = {"CHẨN_ĐOÁN", "THUỐC", "TRIỆU_CHỨNG"}
_MAJOR_SECTION = re.compile(r"(?:^|\n)\s*(\d+)\.\s*([^\n]*)", re.IGNORECASE)
_FAMILY_SUBJECT = re.compile(
    r"\b(?:mẹ|bố|cha|mẹ\s+bệnh\s+nhân|bố\s+bệnh\s+nhân|"
    r"cha\s+bệnh\s+nhân|anh\s+trai|chị\s+gái|em\s+trai|em\s+gái)"
    r"(?:\s+(?:đã|có|bị|mắc))?\s*$",
    re.IGNORECASE,
)
_FAMILY_REPORTING = re.compile(
    r"(?:theo\s+lời\s+(?:người\s+nhà|gia\s+đình)|"
    r"(?:người\s+nhà|gia\s+đình)\s+(?:nhận\s+thấy|cho\s+biết|kể))",
    re.IGNORECASE,
)


def _section_before(text: str, start: int) -> str:
    return text[max(0, start - 500):start].lower()


def _is_historical_section(entity: Entity, raw_text: str) -> bool:
    """Return whether a clinical entity is inside the numbered history block."""
    before = raw_text[:entity.position[0]]
    matches = list(_MAJOR_SECTION.finditer(before))
    if not matches:
        return False
    section = matches[-1]
    number = int(section.group(1))
    heading = section.group(2).casefold()
    return (
        number == 1
        and "tiền sử" in heading
        and "hiện tại" not in heading
        and "bệnh sử hiện tại" not in heading
    )


def _is_family(entity: Entity, raw_text: str) -> bool:
    """Identify concepts belonging to a relative, not merely reported by one."""
    start = entity.position[0]
    line_start = raw_text.rfind("\n", 0, start) + 1
    before = raw_text[line_start:start]
    if re.search(r"(?:tiền\s+sử\s+gia\s+đình|bệnh\s+sử\s+gia\s+đình)", before, re.IGNORECASE):
        return True
    # "Gia đình nhận thấy bệnh nhân khó thở" describes the patient and must
    # not be marked isFamily. The previous implementation also matched "bố"
    # inside "bối cảnh", causing unrelated concepts to become family history.
    if _FAMILY_REPORTING.search(before):
        return False
    return bool(_FAMILY_SUBJECT.search(before[-80:]))


def _is_negated(entity: Entity, raw_text: str) -> bool:
    start, end = entity.position
    line_start = raw_text.rfind("\n", 0, start) + 1
    line_end = raw_text.find("\n", end)
    if line_end < 0:
        line_end = len(raw_text)
    line = raw_text[line_start:line_end]
    local_start, local_end = start - line_start, end - line_start
    mention = line[local_start:local_end]

    # These strings qualify the diagnosis itself; they do not deny that the
    # diagnosis exists (e.g. "xuất huyết ... không do chấn thương").
    if _NON_NEGATING_QUALIFIER.search(mention):
        mention_without_qualifier = _NON_NEGATING_QUALIFIER.sub("", mention)
    else:
        mention_without_qualifier = mention

    before = line[max(0, local_start - 70):local_start]
    if _NEGATION_BREAK.search(before):
        before = _NEGATION_BREAK.split(before)[-1]
    if _NEGATION_RE.search(before):
        return True

    # A cue can be included in the submitted span by some detectors. Only
    # count it when it is a true prefix, never an internal qualifier.
    return bool(
        re.match(
            r"^\s*(?:không(?:\s+(?:có|còn|bị|mắc))?|chưa|phủ\s+nhận)\s+",
            mention_without_qualifier,
            re.IGNORECASE,
        )
    )


def infer_assertions(entity: Entity, raw_text: str) -> list[str]:
    # The organiser defines assertions for diseases, drugs, and symptoms.
    # Test names/results and patient information always carry an empty list.
    if entity.type not in _ASSERTION_ENTITY_TYPES:
        return []
    sentence = enclosing_sentence(raw_text, *entity.position).lower()
    line_start = raw_text.rfind("\n", 0, entity.position[0]) + 1
    line = raw_text[line_start:raw_text.find("\n", entity.position[1]) if raw_text.find("\n", entity.position[1]) >= 0 else len(raw_text)].lower()
    before = _section_before(raw_text, entity.position[0])
    assertions: list[str] = []
    # A drug mention in the medication-history section is historical, but
    # indication symptoms following "điều trị" are not.
    historical = any(cue in sentence for cue in HISTORICAL_CUES)
    if "tiền sử bệnh hiện tại" in sentence or "bệnh sử hiện tại" in sentence:
        historical = False
    # Section cues apply to a medication/diagnosis list only while it is close
    # to the mention. They must not leak into the current-symptom section.
    if entity.type in {"THUỐC", "CHẨN_ĐOÁN"}:
        historical = historical or any(cue in line or cue in before[-90:] for cue in HISTORICAL_CUES)
        if "tiền sử bệnh hiện tại" in line or "bệnh sử hiện tại" in line or re.search(
            r"(?:tiền sử bệnh hiện tại|bệnh sử hiện tại)[\s\S]{0,300}$", before
        ):
            historical = False
    historical = historical or _is_historical_section(entity, raw_text)
    if historical and not (
        entity.type == "TRIỆU_CHỨNG"
        and re.search(r"điều trị\s+[^.]{0,50}" + re.escape(entity.text.lower()), sentence)
    ):
        assertions.append("isHistorical")
    if _is_family(entity, raw_text):
        assertions.append("isFamily")
    if _is_negated(entity, raw_text):
        assertions.append("isNegated")
    return assertions


def attach_assertions(entities: list[Entity], raw_text: str) -> list[Entity]:
    for entity in entities:
        entity.assertions = infer_assertions(entity, raw_text)
    return entities
