from __future__ import annotations

import re
import json
from functools import lru_cache
from pathlib import Path
from typing import Iterable

from .normalize import NormalizedText, normalize_key
from .resources import load_lexicon
from .schema import Entity


_NUMBER = r"\d+(?:[.,]\d+)?(?:\s*-\s*\d+(?:[.,]\d+)?)?"
_UNIT = r"(?:(?:mg|mcg|µg|ml|units?|%)(?!\w)|l(?!\w)|g)"
_ROUTE = r"(?:po|iv|im|sc|sq|oral|intravenous|subcutaneous|topical)"
_SCHEDULE = r"(?:q\d+h(?::prn)?|qam(?::prn)?|qhs(?::prn)?|daily|(?:bid|tid|qid)(?::prn)?|prn)"
_FORM = r"(?:xl|xr|sr|er|ml|tablet(?:s)?|capsule(?:s)?|oral\s+suspension|suspension)"
_DRUG_TAIL = re.compile(
    rf"(?:\s+(?:{_NUMBER}\s*{_UNIT}|{_FORM}|{_ROUTE}|{_SCHEDULE}))*",
    re.IGNORECASE,
)


def _pattern(phrase: str) -> re.Pattern[str]:
    # Spaces in clinical text are frequently duplicated or replaced by newlines.
    parts = [re.escape(p) for p in normalize_key(phrase).split(" ") if p]
    return re.compile(r"(?<!\w)" + r"\s+".join(parts), re.IGNORECASE)


def _acceptable_match(nt: NormalizedText, match: re.Match[str]) -> bool:
    if match.end() >= len(nt.value) or not nt.value[match.end()].isalnum():
        return True
    # Clinical notes occasionally glue a new capitalized sentence to a span,
    # e.g. "khởi phát chuyển dạBệnh sử".
    raw_next = nt.norm_to_raw[match.end()]
    return nt.raw[raw_next].isupper()


def _span(nt: NormalizedText, match: re.Match[str]) -> tuple[int, int]:
    return nt.raw_span(match.start(), match.end())


def _entity(raw: str, pos: tuple[int, int], kind: str, confidence: float, source: str) -> Entity:
    return Entity(
        text=raw[pos[0]:pos[1]],
        type=kind,
        position=pos,
        confidence=confidence,
        source=source,
        candidates=[] if kind in {"CHẨN_ĐOÁN", "THUỐC"} else None,
    )


def _find_lexicon(
    nt: NormalizedText, entries: Iterable[tuple[str, str]], source: str, confidence: float
) -> list[Entity]:
    found: list[Entity] = []
    for phrase, kind in sorted(entries, key=lambda x: len(x[0]), reverse=True):
        for match in _pattern(phrase).finditer(nt.value):
            if not _acceptable_match(nt, match):
                continue
            position = _span(nt, match)
            raw_match = nt.raw[position[0]:position[1]]
            if (
                phrase.isascii()
                and len(phrase) <= 3
                and raw_match.casefold() != phrase.casefold()
            ):
                continue
            found.append(_entity(nt.raw, position, kind, confidence, source))
    return found


def _find_drugs(nt: NormalizedText, drug_names: list[str]) -> list[Entity]:
    found: list[Entity] = []
    for name in sorted(drug_names, key=len, reverse=True):
        for match in _pattern(name).finditer(nt.value):
            if not _acceptable_match(nt, match):
                continue
            end_match = _DRUG_TAIL.match(nt.value, match.end())
            end = end_match.end() if end_match else match.end()
            pos = nt.raw_span(match.start(), end)
            # Do not swallow a neighbouring prose sentence or list item.
            text = nt.raw[pos[0]:pos[1]].rstrip(" \t,;:")
            pos = (pos[0], pos[0] + len(text))
            found.append(_entity(nt.raw, pos, "THUỐC", 0.92, "drug_dictionary"))
    return found


@lru_cache(maxsize=1)
def _rxnorm_aliases() -> set[str]:
    path = Path(__file__).resolve().parent / "resources" / "rxnorm_catalog.json"
    if not path.exists():
        return set()
    catalog = json.loads(path.read_text(encoding="utf-8"))
    aliases = set()
    for alias, row in catalog.get("aliases", {}).items():
        if row.get("tty") not in {"IN", "PIN", "MIN", "BN"}:
            continue
        if re.fullmatch(r"[a-z][a-z0-9' -]{2,}", alias) and len(alias.split()) <= 5:
            aliases.add(alias)
    return aliases


def _find_rxnorm_drugs(nt: NormalizedText, profile: str) -> list[Entity]:
    aliases = _rxnorm_aliases()
    if not aliases:
        return []
    tokens = list(re.finditer(r"(?<!\w)[a-z][a-z0-9'-]*(?!\w)", nt.value))
    found: list[Entity] = []
    dose_re = re.compile(rf"^\s+(?:{_FORM}\s+)*(?:{_NUMBER}\s*{_UNIT})", re.IGNORECASE)
    context_cues = re.compile(
        r"\b(?:thuoc|dung|uong|tiem|truyen|dieu tri|chi dinh|toa|medication)\b",
        re.IGNORECASE,
    )
    non_drug_aliases = {
        "alanine",
        "aspartate",
        "caffeine",
        "cholesterol",
        "creatinine",
        "glucose",
        "guaiac",
        "lactate",
        "lipase",
    }
    for i in range(len(tokens)):
        for size in range(1, min(5, len(tokens) - i) + 1):
            group = tokens[i:i + size]
            alias = " ".join(m.group(0) for m in group)
            if alias not in aliases:
                continue
            start, end = group[0].start(), group[-1].end()
            after = nt.value[end:end + 80]
            has_dose = bool(dose_re.match(after))
            raw_start, raw_end = nt.raw_span(start, end)
            line_start = nt.raw.rfind("\n", 0, raw_start) + 1
            line_end = nt.raw.find("\n", raw_end)
            if line_end < 0:
                line_end = len(nt.raw)
            line_context_before = normalize_key(nt.raw[line_start:raw_start])
            prior_lines = [
                normalize_key(value)
                for value in nt.raw[:line_start].splitlines()
                if value.strip()
            ]
            previous_context = prior_lines[-1] if prior_lines else ""
            in_med_context = bool(context_cues.search(line_context_before[-120:]))
            previous_is_med_heading = bool(
                len(previous_context.split()) <= 8
                and re.search(r"(?:thuoc|xu tri thuoc|medication)", previous_context)
            )
            in_med_context = in_med_context or previous_is_med_heading
            if alias in non_drug_aliases and not has_dose:
                continue
            if size == 1 and len(alias) < 5 and not (has_dose or in_med_context):
                continue
            tail = _DRUG_TAIL.match(nt.value, end)
            full_end = tail.end() if tail else end
            pos = nt.raw_span(start, full_end)
            text = nt.raw[pos[0]:pos[1]].rstrip(" \t,;:")
            pos = (pos[0], pos[0] + len(text))
            found.append(_entity(nt.raw, pos, "THUỐC", 0.88 if has_dose else 0.68, "rxnorm_alias"))
    return found


def _find_section_entities(raw: str) -> list[Entity]:
    found: list[Entity] = []
    section: str | None = None
    offset = 0
    symptom_heading = re.compile(r"triệu chứng|đặc điểm triệu chứng|lý do nhập viện", re.IGNORECASE)
    diagnosis_heading = re.compile(r"bệnh lý (?:mạn|mãn)|các bệnh đã|chẩn đoán", re.IGNORECASE)
    reset_heading = re.compile(r"^\s*\d+\.\s")
    stop = {
        "n/a",
        "không có triệu chứng trước đó",
        "các triệu chứng hiện tại",
        "vị trí",
        "mức độ nghiêm trọng",
        "thời gian",
        "tần suất",
        "chiếu xạ",
        "các triệu chứng liên quan",
        "lan tỏa",
        "tính chất",
        "màu sắc",
        "triệu chứng liên quan",
        "triệu chứng kèm theo",
        "yếu tố làm nặng thêm",
        "yếu tố làm giảm",
        "chiếu r xạ",
        "ăn uống",
        "bên trái",
        "liên tục",
    }
    action_prefix = re.compile(
        r"^(?:bệnh nhân|được|cảm thấy|không liên quan|các yếu tố|"
        r"xét nghiệm|chụp|phân tích|monitor|lên lịch|sau đó|ở nhà|"
        r"bắt đầu|tỉnh dậy|ước tính|quyết định|tất cả|tiền sử|"
        r"khởi phát|vị trí|mức độ|thời gian|tần suất|chiếu xạ|"
        r"các triệu chứng liên quan|triệu chứng (?:liên quan|kèm theo|cách đây)|"
        r"yếu tố làm|thứ tự phát triển|tiến triển bệnh|sau khi|khoảng|"
        r"cần phải|trong năm|gần đây|khi |nhập viện|hôm nay|"
        r"khó khăn khi|nhiều lần|thở oxy|\d+\s)",
        re.IGNORECASE,
    )
    for line in raw.splitlines(keepends=True):
        stripped = line.strip()
        bullet = re.match(r"^\s*[-•]\s+(.+)", line.rstrip("\r\n"))
        if symptom_heading.search(stripped):
            section = "TRIỆU_CHỨNG"
        elif diagnosis_heading.search(stripped) and not re.search(
            r"chẩn đoán (?:hình ảnh|khác)", stripped, re.IGNORECASE
        ):
            section = "CHẨN_ĐOÁN"
        elif (
            reset_heading.search(stripped)
            or (
                not bullet
                and stripped
                and len(stripped.split()) <= 10
                and not stripped.endswith(".")
            )
        ):
            section = None
        if bullet and section:
            phrase = re.split(r"[:;(]", bullet.group(1), maxsplit=1)[0].strip(" -*")
            words = phrase.split()
            if (
                phrase.casefold() not in stop
                and 1 <= len(words) <= 6
                and not action_prefix.search(phrase)
            ):
                relative = line.find(phrase)
                start = offset + relative
                end = start + len(phrase)
                found.append(_entity(raw, (start, end), section, 0.56, "section_rule"))
        offset += len(line)
    return found


def _find_labs(nt: NormalizedText, lab_names: list[str]) -> list[Entity]:
    found: list[Entity] = []
    for name in sorted(lab_names, key=len, reverse=True):
        for match in _pattern(name).finditer(nt.value):
            if not _acceptable_match(nt, match):
                continue
            pos = _span(nt, match)
            found.append(_entity(nt.raw, pos, "TÊN_XÉT_NGHIỆM", 0.82, "lab_dictionary"))
            tail = nt.value[match.end():match.end() + 90]
            value_match = re.search(
                r"(?:\s*[:=]\s*|\s+)(-?\d+(?:[.,]\d+)?(?:\s*-\s*\d+(?:[.,]\d+)?)?)",
                tail,
            )
            if value_match:
                vpos = nt.raw_span(
                    match.end() + value_match.start(1),
                    match.end() + value_match.end(1),
                )
                found.append(_entity(nt.raw, vpos, "KẾT_QUẢ_XÉT_NGHIỆM", 0.78, "lab_value"))
    return found


def _find_patient_info(nt: NormalizedText) -> list[Entity]:
    found: list[Entity] = []
    patterns = [
        r"\b\d{1,3}\s*tuổi\b",
        r"\b(?:bệnh nhân\s+)?(?:nam|nữ)\b",
        r"\b(?:mã|id)\s*(?:bệnh nhân|bệnh án)\s*[:#]?\s*[A-Za-z0-9-]+\b",
    ]
    for expression in patterns:
        for match in re.finditer(expression, nt.value, re.IGNORECASE):
            found.append(_entity(nt.raw, _span(nt, match), "THÔNG_TIN_BỆNH_NHÂN", 0.7, "patient_regex"))
    return found


def _dedupe_and_resolve(entities: list[Entity]) -> list[Entity]:
    priority = {
        "THUỐC": 6,
        "CHẨN_ĐOÁN": 5,
        "TÊN_XÉT_NGHIỆM": 4,
        "KẾT_QUẢ_XÉT_NGHIỆM": 4,
        "TRIỆU_CHỨNG": 3,
        "THÔNG_TIN_BỆNH_NHÂN": 2,
    }
    # Exact duplicates: keep the strongest source/confidence.
    best: dict[tuple[int, int, str], Entity] = {}
    for entity in entities:
        key = (*entity.position, entity.type)
        if key not in best or entity.confidence > best[key].confidence:
            best[key] = entity
    values = sorted(best.values(), key=lambda e: (e.position[0], -(e.position[1] - e.position[0]), -priority[e.type]))
    kept: list[Entity] = []
    for entity in values:
        # A longer entity of the same semantic type supersedes a strict subspan.
        replaced = False
        for idx, existing in enumerate(kept):
            same_type = existing.type == entity.type
            contained = (
                existing.position[0] <= entity.position[0]
                and entity.position[1] <= existing.position[1]
            )
            if same_type and contained and existing.position != entity.position:
                if entity.confidence > existing.confidence:
                    kept.pop(idx)
                    continue
                replaced = True
                break
        if not replaced:
            kept.append(entity)
    return sorted(kept, key=lambda e: e.position)


def detect_entities(text: str, lexicon: dict | None = None, profile: str = "precision") -> list[Entity]:
    lex = lexicon or load_lexicon()
    from .normalize import normalize_with_map

    nt = normalize_with_map(text)
    entities: list[Entity] = []
    entities.extend(
        _find_lexicon(
            nt,
            [(phrase, "TRIỆU_CHỨNG") for phrase in lex.get("symptoms", {})],
            "symptom_dictionary",
            0.82,
        )
    )
    entities.extend(
        _find_lexicon(
            nt,
            [(phrase, "CHẨN_ĐOÁN") for phrase in lex.get("diagnoses", {})],
            "diagnosis_dictionary",
            0.9,
        )
    )
    entities.extend(_find_drugs(nt, list(lex.get("drugs", []))))
    if profile not in {"baseline", "baseline_strength", "section_only"}:
        entities.extend(_find_rxnorm_drugs(nt, profile))
    entities.extend(_find_labs(nt, list(lex.get("lab_names", []))))
    entities.extend(_find_patient_info(nt))
    if profile in {"recall", "section_only"}:
        entities.extend(_find_section_entities(text))
    return _dedupe_and_resolve(entities)
