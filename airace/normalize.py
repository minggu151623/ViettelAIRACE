from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class NormalizedText:
    raw: str
    value: str
    norm_to_raw: tuple[int, ...]

    def raw_span(self, start: int, end: int) -> tuple[int, int]:
        if start >= end or not self.norm_to_raw:
            return (0, 0)
        start = max(0, min(start, len(self.norm_to_raw) - 1))
        end = max(start + 1, min(end, len(self.norm_to_raw)))
        return (self.norm_to_raw[start], self.norm_to_raw[end - 1] + 1)


def _strip_marks(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFD", value)
        if unicodedata.category(ch) != "Mn"
    )


def normalize_with_map(raw: str) -> NormalizedText:
    chars: list[str] = []
    mapping: list[int] = []
    for idx, char in enumerate(raw):
        expanded = unicodedata.normalize("NFKC", char).casefold()
        expanded = _strip_marks(expanded)
        for out in expanded:
            chars.append(out)
            mapping.append(idx)
    return NormalizedText(raw=raw, value="".join(chars), norm_to_raw=tuple(mapping))


def normalize_key(value: str) -> str:
    return re.sub(r"\s+", " ", _strip_marks(unicodedata.normalize("NFKC", value).casefold())).strip()


def sentence_bounds(text: str) -> list[tuple[int, int]]:
    bounds: list[tuple[int, int]] = []
    start = 0
    for match in re.finditer(r"[.!?;\n]+", text):
        end = match.end()
        if text[start:end].strip():
            bounds.append((start, end))
        start = end
    if text[start:].strip():
        bounds.append((start, len(text)))
    return bounds


def enclosing_sentence(text: str, start: int, end: int) -> str:
    for left, right in sentence_bounds(text):
        if left <= start < right:
            return text[left:right]
    return text[max(0, start - 160):min(len(text), end + 160)]

