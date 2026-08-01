from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from .schema import Entity


@dataclass(frozen=True)
class Proposal:
    """Non-submission record retaining model evidence for calibrated merging."""

    text: str
    type: str
    position: tuple[int, int]
    confidence: float
    source: str
    assertions: tuple[str, ...] = ()
    candidates: tuple[str, ...] | None = None

    @classmethod
    def from_entity(cls, entity: Entity) -> "Proposal":
        return cls(
            text=entity.text,
            type=entity.type,
            position=entity.position,
            confidence=float(entity.confidence),
            source=entity.source,
            assertions=tuple(entity.assertions),
            candidates=(
                tuple(entity.candidates or [])
                if entity.type in {"CHẨN_ĐOÁN", "THUỐC"}
                else None
            ),
        )

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Proposal":
        return cls(
            text=str(value["text"]),
            type=str(value["type"]),
            position=(int(value["position"][0]), int(value["position"][1])),
            confidence=float(value.get("confidence", 0.0)),
            source=str(value.get("source", "unknown")),
            assertions=tuple(value.get("assertions") or ()),
            candidates=(
                tuple(value.get("candidates") or [])
                if value.get("candidates") is not None
                else None
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["position"] = [self.position[0], self.position[1]]
        value["assertions"] = list(self.assertions)
        if self.candidates is not None:
            value["candidates"] = list(self.candidates)
        return value

    def to_entity(self) -> Entity:
        return Entity(
            text=self.text,
            type=self.type,
            assertions=list(self.assertions),
            position=self.position,
            candidates=list(self.candidates) if self.candidates is not None else None,
            confidence=self.confidence,
            source=self.source,
        )


def dump_proposals(proposals: Iterable[Proposal], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            [proposal.to_dict() for proposal in proposals],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def load_proposals(path: str | Path) -> list[Proposal]:
    return [
        Proposal.from_dict(value)
        for value in json.loads(Path(path).read_text(encoding="utf-8"))
    ]
