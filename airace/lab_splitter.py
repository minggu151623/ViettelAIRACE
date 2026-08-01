from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from .normalize import normalize_key, normalize_with_map


_HSPACE = r"[ \t]"
_NUMBER = rf"-?\d+(?:[.,]\d+)?(?:{_HSPACE}*-{_HSPACE}*-?\d+(?:[.,]\d+)?)?"
_UNIT = (
    r"(?:%|mg/dl|mmol/l|µmol/l|umol/l|g/dl|g/l|u/l|iu/l|miu/l|"
    r"ng/ml|ng/l|pg/ml|mmhg|bpm|/mm3|/µl|/ul)"
)
_VALUE = re.compile(rf"(?P<value>{_NUMBER}(?:{_HSPACE}*{_UNIT})?)", re.IGNORECASE)
_FORWARD_SEPARATOR = re.compile(
    rf"{_HSPACE}*(?::|=|\bla\b)?{_HSPACE}*",
    re.IGNORECASE,
)
_ACTION_CONTEXT = re.compile(
    r"\b(?:bo sung|dieu tri|dung|uong|truyen|tiem|lieu)\b",
    re.IGNORECASE,
)
_BULLET_ONLY = re.compile(r"^[ \t]*(?:[-*•][ \t]*)?$")


@dataclass(frozen=True)
class LabPair:
    name: tuple[int, int]
    result: tuple[int, int]


def _name_pattern(name: str) -> re.Pattern[str]:
    parts = [re.escape(part) for part in normalize_key(name).split() if part]
    return re.compile(r"(?<!\w)" + r"\s+".join(parts) + r"(?!\w)", re.IGNORECASE)


def find_numeric_lab_pairs(raw_text: str, lab_names: Iterable[str]) -> list[LabPair]:
    """Find conservative, independent test-name/value spans.

    This helper intentionally covers only a single numeric value adjacent to a
    known laboratory name. It does not interpret panels, textual findings, or
    imaging conclusions.
    """

    normalized = normalize_with_map(raw_text)
    proposed: list[tuple[int, int, int, int]] = []
    for name in sorted(set(lab_names), key=lambda item: (-len(normalize_key(item)), item)):
        for match in _name_pattern(name).finditer(normalized.value):
            line_start = normalized.value.rfind("\n", 0, match.start()) + 1
            line_prefix = normalized.value[line_start:match.start()]

            # name -> optional ":"/"="/"là" -> numeric value
            tail = normalized.value[match.end():match.end() + 48]
            separator = _FORWARD_SEPARATOR.match(tail)
            if separator and not _ACTION_CONTEXT.search(line_prefix):
                value = _VALUE.match(tail, separator.end())
                if value:
                    raw_remainder = tail[value.end("value"):]
                    remainder = raw_remainder.lstrip(" \t")
                    if (
                        remainder.startswith(("->", "-->", "→"))
                        or (raw_remainder and raw_remainder[0].isalpha())
                    ):
                        continue
                    ns, ne = normalized.raw_span(match.start(), match.end())
                    vs, ve = normalized.raw_span(
                        match.end() + value.start("value"),
                        match.end() + value.end("value"),
                    )
                    proposed.append((ns, ne, vs, ve))

            # numeric value -> whitespace -> name (for rows such as
            # "80 neutrophil"). Keep the backward window deliberately short.
            head_start = max(0, match.start() - 32)
            head = normalized.value[head_start:match.start()]
            backward = re.search(
                rf"(?P<value>{_NUMBER}(?:{_HSPACE}*{_UNIT})?){_HSPACE}+$",
                head,
                re.IGNORECASE,
            )
            if backward:
                value_start = head_start + backward.start("value")
                segment_start = max(
                    line_start,
                    normalized.value.rfind(";", line_start, value_start) + 1,
                )
                before_value = normalized.value[segment_start:value_start]
                # A value-before-name row must begin with the value (apart from
                # indentation/bullet markers) within its line/semicolon
                # segment. This rejects "rr 14 spo2".
                if _BULLET_ONLY.fullmatch(before_value):
                    ns, ne = normalized.raw_span(match.start(), match.end())
                    vs, ve = normalized.raw_span(
                        value_start,
                        head_start + backward.end("value"),
                    )
                    proposed.append((ns, ne, vs, ve))

    # Prefer the longest exact name at one location, then remove duplicate pairs.
    best_name: dict[tuple[int, int], tuple[int, int, int, int]] = {}
    for item in proposed:
        name_start, name_end, value_start, value_end = item
        key = (value_start, value_end)
        current = best_name.get(key)
        if current is None or name_end - name_start > current[1] - current[0]:
            best_name[key] = item

    pairs = {
        LabPair(name=(ns, ne), result=(vs, ve))
        for ns, ne, vs, ve in best_name.values()
        if raw_text[ns:ne].strip() and raw_text[vs:ve].strip()
    }
    return sorted(pairs, key=lambda pair: (pair.name[0], pair.result[0]))
