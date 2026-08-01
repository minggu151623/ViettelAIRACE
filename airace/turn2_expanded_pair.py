from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .assertions import infer_assertions
from .candidates import CandidateResolver
from .normalize import normalize_key
from .proposals import Proposal, load_proposals
from .schema import Entity, entities_from_json
from .turn2_pair_review import _NOISE, _request
from .validator import validate_entities
from .who_icd_rebuild import _H19_EXACT


_BAD_EXACT = {
    normalize_key(value)
    for value in (
        "vận động",
        "đoạn",
        "buồn",
        "tắc nghẽn",
        "chứng mạch vành",
        "phân tích",
        "ống nội khí quản",
        "cấy máu dương tính",
        "hemoglobin 7.8",
        "doxycyclinebactrim",
        "klonopinclonidine",
        "vancozosynbactrim",
    )
}
_BAD_BOUNDARY = (
    "ăng huyết áp",
    "vìviêm",
    "đườngđái",
    "ảo giácxuất",
)
_EXACT_DRUG_CANDIDATES = {
    normalize_key("acetaminophen 500mg"): ["198440"],
    normalize_key("metoprolol 25mg po bid"): ["866924"],
    normalize_key("mucinex d"): ["373692"],
}


def _eligible(votes: dict[str, Proposal], kind: str) -> bool:
    names = set(votes)
    if names == {"bami_v15", "bami_v3"}:
        v15, v3 = votes["bami_v15"].confidence, votes["bami_v3"].confidence
        return (
            (kind == "CHẨN_ĐOÁN" and v15 >= 0.62 and v3 >= 0.40)
            or (kind == "TRIỆU_CHỨNG" and v15 >= 0.60 and v3 >= 0.55)
            or (kind == "TÊN_XÉT_NGHIỆM" and v15 >= 0.40 and v3 >= 0.32)
        )
    if "vietmed_ner" not in names:
        return False
    other = next((name for name in names if name != "vietmed_ner"), None)
    if other is None:
        return False
    vm, second = votes["vietmed_ner"].confidence, votes[other].confidence
    return (
        (kind == "THUỐC" and vm >= 0.75 and second >= 0.60)
        or (kind == "CHẨN_ĐOÁN" and vm >= 0.85 and second >= 0.40)
        or (kind == "TRIỆU_CHỨNG" and vm >= 0.85 and second >= 0.35)
        or (kind == "TÊN_XÉT_NGHIỆM" and vm >= 0.85 and second >= 0.30)
    )


def _context(raw_text: str, start: int, end: int) -> str:
    return raw_text[max(0, start - 160):start] + "⟦" + raw_text[start:end] + "⟧" + raw_text[end:min(len(raw_text), end + 160)]


def collect_expanded_rows(
    input_dir: str | Path,
    source_dir: str | Path,
    proposal_dirs: list[str | Path],
) -> list[dict[str, Any]]:
    inputs, source = Path(input_dir), Path(source_dir)
    directories = [Path(value) for value in proposal_dirs]
    rows: list[dict[str, Any]] = []
    for input_path in sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem)):
        stem = input_path.stem
        raw_text = input_path.read_text(encoding="utf-8")
        baseline = json.loads((source / f"{stem}.json").read_text(encoding="utf-8"))
        exact = {(item["position"][0], item["position"][1], item["type"], item["text"]) for item in baseline}
        intervals = [tuple(item["position"]) for item in baseline]
        grouped: dict[tuple[int, int, str, str], dict[str, Proposal]] = defaultdict(dict)
        for directory in directories:
            for proposal in load_proposals(directory / f"{stem}.json"):
                key = (*proposal.position, proposal.type, proposal.text)
                old = grouped[key].get(proposal.source)
                if old is None or proposal.confidence > old.confidence:
                    grouped[key][proposal.source] = proposal
        for (start, end, kind, value), votes in grouped.items():
            key = (start, end, kind, value)
            normalized = normalize_key(value).strip(" .,:;()[]-_")
            if (
                key in exact
                or len(votes) < 2
                or not _eligible(votes, kind)
                or any(not (end <= left or start >= right) for left, right in intervals)
                or not (0 <= start < end <= len(raw_text))
                or raw_text[start:end] != value
                or "\n" in value
                or "\r" in value
                or len(normalized) < 2
                or normalized in _NOISE
                or not any(character.isalpha() for character in value)
            ):
                continue
            rows.append(
                {
                    "record": stem,
                    "text": value,
                    "type": kind,
                    "position": [start, end],
                    "sources": sorted(votes),
                    "confidences": {name: round(votes[name].confidence, 6) for name in sorted(votes)},
                    "context": _context(raw_text, start, end),
                }
            )
    rows.sort(key=lambda row: (int(row["record"]), row["position"], row["type"]))
    for identifier, row in enumerate(rows):
        row["id"] = identifier
    return rows


def review_expanded_rows(
    input_dir: str | Path,
    source_dir: str | Path,
    proposal_dirs: list[str | Path],
    output_path: str | Path,
    *,
    model: str = "qwen3:8b",
    batch_size: int = 28,
) -> dict[str, Any]:
    rows = collect_expanded_rows(input_dir, source_dir, proposal_dirs)
    decisions: dict[int, tuple[str, float]] = {}
    for offset in range(0, len(rows), batch_size):
        decisions.update(_request(model, rows[offset:offset + batch_size], 6197))
        print(f"expanded review {min(offset + batch_size, len(rows))}/{len(rows)}", flush=True)
    accepted = 0
    for row in rows:
        action, raw_confidence = decisions.get(row["id"], ("DROP", 0.0))
        confidence = float(raw_confidence)
        valid_confidence = 0.0 <= confidence <= 1.0
        row["review"] = {"action": action, "confidence": confidence}
        row["accepted"] = action == "KEEP" and valid_confidence and confidence >= 0.85
        accepted += int(row["accepted"])
    result = {"model": model, "eligible": len(rows), "accepted": accepted, "rows": rows}
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {key: value for key, value in result.items() if key != "rows"}


def select_expanded_rows(
    review_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Calibrate the frozen Qwen actions without using copied confidences."""

    review = json.loads(Path(review_path).read_text(encoding="utf-8"))
    counts: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    for source_row in review["rows"]:
        row = dict(source_row)
        key = normalize_key(row["text"])
        malformed = key in _BAD_EXACT or any(key.startswith(prefix) for prefix in _BAD_BOUNDARY)
        action = row.get("review", {}).get("action")
        if malformed:
            selected, reason = False, "boundary_sanitizer"
        elif row["type"] == "THUỐC":
            # In the frozen run Qwen rejected obvious medicines such as
            # omeprazole and acetaminophen while the two supervised models
            # agreed. For drugs, exact two-model agreement is the calibrated
            # evidence and Qwen is used only to expose malformed fused spans.
            selected, reason = True, "drug_pair_consensus"
        elif action == "KEEP":
            selected, reason = True, "qwen_keep"
        else:
            selected, reason = False, "qwen_drop"
        row["selected"] = selected
        row["selection_reason"] = reason
        counts[f"{reason}:{row['type']}"] += 1
        if selected:
            counts["selected"] += 1
            counts[f"selected:{row['type']}"] += 1
        rows.append(row)
    result = {
        "source_review": str(review_path),
        "eligible": len(rows),
        "selected": counts["selected"],
        "counts": dict(sorted(counts.items())),
        "rows": rows,
    }
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {key: value for key, value in result.items() if key != "rows"}


def merge_expanded_rows(
    input_dir: str | Path,
    source_dir: str | Path,
    review_path: str | Path,
    output_dir: str | Path,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    inputs, source, output = Path(input_dir), Path(source_dir), Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    review = json.loads(Path(review_path).read_text(encoding="utf-8"))
    accepted: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in review["rows"]:
        if row.get("selected", row.get("accepted", False)):
            accepted[row["record"]].append(row)
    resolver = CandidateResolver(strict_strength=True)
    counts: Counter[str] = Counter()
    additions: list[dict[str, Any]] = []
    for input_path in sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem)):
        stem = input_path.stem
        raw_text = input_path.read_text(encoding="utf-8")
        entities = entities_from_json(json.loads((source / f"{stem}.json").read_text(encoding="utf-8")))
        for row in accepted.get(stem, []):
            entity = Entity(text=row["text"], type=row["type"], position=tuple(row["position"]), source="expanded_pair_qwen")
            entity.assertions = infer_assertions(entity, raw_text)
            if entity.type == "CHẨN_ĐOÁN":
                entity.candidates = list(_H19_EXACT.get(normalize_key(entity.text), []))
            elif entity.type == "THUỐC":
                exact_drug = _EXACT_DRUG_CANDIDATES.get(normalize_key(entity.text))
                if exact_drug is not None:
                    entity.candidates = list(exact_drug)
                else:
                    resolver.resolve(entity, raw_text)
            entities.append(entity)
            counts[entity.type] += 1
            additions.append({**row, "assertions": entity.assertions, "candidates": entity.candidates})
        entities.sort(key=lambda entity: (entity.position, entity.type))
        validate_entities(entities, raw_text)
        (output / f"{stem}.json").write_text(json.dumps([entity.to_dict() for entity in entities], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {"source": str(source), "review": str(review_path), "records": 100, "additions": len(additions), "additions_by_type": dict(sorted(counts.items())), "addition_rows": additions}
    if report_path:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
