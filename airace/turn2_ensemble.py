from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .assertions import infer_assertions
from .normalize import normalize_key
from .proposals import Proposal, load_proposals
from .schema import Entity, entities_from_json
from .validator import validate_entities


_ELIGIBLE_TYPES = {
    "CHẨN_ĐOÁN",
    "TRIỆU_CHỨNG",
    "TÊN_XÉT_NGHIỆM",
    "KẾT_QUẢ_XÉT_NGHIỆM",
    "THÔNG_TIN_BỆNH_NHÂN",
}
_GENERIC_NOISE = {
    "benh",
    "benh nhan",
    "chan doan",
    "trieu chung",
    "xet nghiem",
    "ket qua",
    "dieu tri",
    "thuoc",
    "theo doi",
    "nhap vien",
    "xuat vien",
}


def _key(proposal: Proposal) -> tuple[int, int, str, str]:
    return (*proposal.position, proposal.type, proposal.text)


def _safe_exact_candidates(entity: Entity, diagnoses: dict[str, list[str]]) -> list[str]:
    """Return codes only for a literal normalized alias, never fuzzy containment."""
    if entity.type != "CHẨN_ĐOÁN":
        return []
    return list(diagnoses.get(normalize_key(entity.text), ()))[:2]


def _reject_reason(entity: Entity, raw_text: str) -> str | None:
    start, end = entity.position
    if entity.type not in _ELIGIBLE_TYPES:
        return "ineligible_type"
    if not (0 <= start < end <= len(raw_text)):
        return "invalid_position"
    if raw_text[start:end] != entity.text:
        return "offset_mismatch"
    if "\n" in entity.text or "\r" in entity.text:
        return "cross_line"
    key = normalize_key(entity.text).strip(" .,:;()[]-_")
    if len(key) < 2:
        return "too_short"
    if key in _GENERIC_NOISE:
        return "generic_noise"
    if not any(character.isalpha() for character in entity.text):
        return "no_letters"
    return None


def build_turn2_ensemble(
    input_dir: str | Path,
    source_dir: str | Path,
    proposal_dirs: list[str | Path],
    output_dir: str | Path,
    report_path: str | Path | None = None,
    *,
    min_sources: int = 3,
) -> dict[str, Any]:
    inputs = Path(input_dir)
    source = Path(source_dir)
    proposal_paths = [Path(value) for value in proposal_dirs]
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    # Importing the resolver only for its exact curated ICD alias table avoids
    # the fuzzy substring fallback used by general inference.
    from .candidates import CandidateResolver

    diagnoses = CandidateResolver().diagnoses
    counts: Counter[str] = Counter()
    support_combinations: Counter[str] = Counter()
    rejected: Counter[str] = Counter()
    additions: list[dict[str, Any]] = []

    records = sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem))
    for input_path in records:
        stem = input_path.stem
        raw_text = input_path.read_text(encoding="utf-8")
        baseline = entities_from_json(
            json.loads((source / f"{stem}.json").read_text(encoding="utf-8"))
        )
        baseline_keys = {
            (*entity.position, entity.type, entity.text) for entity in baseline
        }
        grouped: dict[tuple[int, int, str, str], dict[str, Proposal]] = defaultdict(dict)
        for directory in proposal_paths:
            for proposal in load_proposals(directory / f"{stem}.json"):
                current = grouped[_key(proposal)].get(proposal.source)
                if current is None or proposal.confidence > current.confidence:
                    grouped[_key(proposal)][proposal.source] = proposal

        accepted: list[Entity] = []
        for key, by_source in grouped.items():
            if key in baseline_keys:
                continue
            if len(by_source) < min_sources:
                rejected["insufficient_support"] += 1
                continue
            start, end, kind, text = key
            entity = Entity(
                text=text,
                type=kind,
                position=(start, end),
                confidence=sum(value.confidence for value in by_source.values()) / len(by_source),
                source="ensemble_exact",
            )
            reason = _reject_reason(entity, raw_text)
            if reason:
                rejected[reason] += 1
                continue
            entity.assertions = infer_assertions(entity, raw_text)
            if entity.type == "CHẨN_ĐOÁN":
                entity.candidates = _safe_exact_candidates(entity, diagnoses)
            accepted.append(entity)
            sources = tuple(sorted(by_source))
            support_combinations["+".join(sources)] += 1
            counts[entity.type] += 1
            additions.append(
                {
                    "record": stem,
                    "text": entity.text,
                    "type": entity.type,
                    "position": [start, end],
                    "sources": list(sources),
                    "confidences": {
                        name: round(by_source[name].confidence, 6) for name in sources
                    },
                    "assertions": entity.assertions,
                    "candidates": entity.candidates,
                }
            )

        merged = sorted(baseline + accepted, key=lambda item: (item.position, item.type))
        validate_entities(merged, raw_text)
        (output / f"{stem}.json").write_text(
            json.dumps([entity.to_dict() for entity in merged], ensure_ascii=False, indent=2)
            + "\n",
            encoding="utf-8",
        )

    report = {
        "records": len(records),
        "source": str(source),
        "proposal_dirs": [str(value) for value in proposal_paths],
        "min_sources": min_sources,
        "additions": len(additions),
        "additions_by_type": dict(sorted(counts.items())),
        "support_combinations": dict(sorted(support_combinations.items())),
        "rejected": dict(sorted(rejected.items())),
        "addition_rows": additions,
    }
    if report_path:
        destination = Path(report_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return report
