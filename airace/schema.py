from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


ENTITY_TYPES = {
    "CHẨN_ĐOÁN",
    "TRIỆU_CHỨNG",
    "TÊN_XÉT_NGHIỆM",
    "KẾT_QUẢ_XÉT_NGHIỆM",
    "THUỐC",
    "THÔNG_TIN_BỆNH_NHÂN",
}
ASSERTIONS = {"isNegated", "isFamily", "isHistorical"}
CANDIDATE_TYPES = {"CHẨN_ĐOÁN", "THUỐC"}


@dataclass
class Entity:
    text: str
    type: str
    assertions: list[str] = field(default_factory=list)
    position: tuple[int, int] = (0, 0)
    candidates: list[str] | None = None
    confidence: float = 0.0
    source: str = "rule"

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "text": self.text,
            "type": self.type,
        }
        if self.type in CANDIDATE_TYPES:
            out["candidates"] = list(dict.fromkeys(self.candidates or []))
        out["assertions"] = list(dict.fromkeys(self.assertions))
        out["position"] = [int(self.position[0]), int(self.position[1])]
        return out

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Entity":
        return cls(
            text=str(value["text"]),
            type=str(value["type"]),
            assertions=list(value.get("assertions") or []),
            position=(int(value["position"][0]), int(value["position"][1])),
            candidates=list(value.get("candidates") or [])
            if "candidates" in value
            else None,
        )


def entities_from_json(values: Iterable[dict[str, Any]]) -> list[Entity]:
    return [Entity.from_dict(v) for v in values]
