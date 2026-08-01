from __future__ import annotations

import json
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .assertions import infer_assertions
from .normalize import normalize_key
from .proposals import Proposal, load_proposals
from .schema import Entity, entities_from_json
from .validator import validate_entities


_FLOORS = {
    "CHẨN_ĐOÁN": 0.58,
    "TRIỆU_CHỨNG": 0.60,
    "TÊN_XÉT_NGHIỆM": 0.38,
}
_NOISE = {
    "benh",
    "benh nhan",
    "chan doan",
    "trieu chung",
    "xet nghiem",
    "ket qua",
    "dieu tri",
    "thuoc",
    "theo doi",
}
_SCHEMA = {
    "type": "object",
    "properties": {
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "action": {"type": "string", "enum": ["KEEP", "DROP"]},
                    "confidence": {"type": "number"},
                },
                "required": ["id", "action", "confidence"],
            },
        }
    },
    "required": ["decisions"],
}
_PROMPT = """Bạn kiểm định annotation NER hồ sơ y khoa tiếng Việt.
Mỗi row là một span cố định đã được hai model độc lập đồng ý. Chỉ KEEP hoặc DROP;
không sửa text, type hay position.

KEEP khi toàn bộ span là một mention lâm sàng đúng với type:
- CHẨN_ĐOÁN: bệnh, hội chứng hoặc tình trạng bệnh lý;
- TRIỆU_CHỨNG: triệu chứng, dấu hiệu hoặc than phiền của bệnh nhân;
- TÊN_XÉT_NGHIỆM: tên xét nghiệm, chẩn đoán hình ảnh hay thủ thuật chẩn đoán.

Mention trong tiền sử, phủ định, mô tả kiến thức hoặc lặp lại vẫn được KEEP. DROP
khi span chỉ là tiêu đề chung, giải phẫu đơn thuần, hành động điều trị, kết quả xét
nghiệm, từ quá chung, boundary cụt/dính, hoặc type rõ ràng sai. Đánh giá riêng từng
row từ context. Trả đủ đúng một decision cho mọi id theo JSON schema. /no_think"""


def _context(raw_text: str, start: int, end: int) -> str:
    left = max(0, start - 140)
    right = min(len(raw_text), end + 140)
    return raw_text[left:start] + "⟦" + raw_text[start:end] + "⟧" + raw_text[end:right]


def collect_pair_rows(
    input_dir: str | Path,
    source_dir: str | Path,
    proposal_dirs: list[str | Path],
) -> list[dict[str, Any]]:
    inputs, source = Path(input_dir), Path(source_dir)
    proposal_paths = [Path(value) for value in proposal_dirs]
    rows: list[dict[str, Any]] = []
    for input_path in sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem)):
        stem = input_path.stem
        raw_text = input_path.read_text(encoding="utf-8")
        baseline = entities_from_json(
            json.loads((source / f"{stem}.json").read_text(encoding="utf-8"))
        )
        baseline_keys = {(*entity.position, entity.type, entity.text) for entity in baseline}
        grouped: dict[tuple[int, int, str, str], dict[str, Proposal]] = defaultdict(dict)
        for directory in proposal_paths:
            for proposal in load_proposals(directory / f"{stem}.json"):
                key = (*proposal.position, proposal.type, proposal.text)
                current = grouped[key].get(proposal.source)
                if current is None or proposal.confidence > current.confidence:
                    grouped[key][proposal.source] = proposal
        for key, votes in grouped.items():
            start, end, kind, text = key
            if key in baseline_keys or len(votes) != 2 or kind not in _FLOORS:
                continue
            if "vietmed_ner" not in votes:
                continue
            bami = next((name for name in votes if name in {"bami_v15", "bami_v3"}), None)
            if bami is None:
                continue
            if votes["vietmed_ner"].confidence < 0.85 or votes[bami].confidence < _FLOORS[kind]:
                continue
            normalized = normalize_key(text).strip(" .,:;()[]-_")
            if (
                not (0 <= start < end <= len(raw_text))
                or raw_text[start:end] != text
                or "\n" in text
                or "\r" in text
                or len(normalized) < 2
                or normalized in _NOISE
                or not any(character.isalpha() for character in text)
            ):
                continue
            rows.append(
                {
                    "record": stem,
                    "text": text,
                    "type": kind,
                    "position": [start, end],
                    "sources": sorted(votes),
                    "confidences": {
                        name: round(votes[name].confidence, 6) for name in sorted(votes)
                    },
                    "context": _context(raw_text, start, end),
                }
            )
    rows.sort(key=lambda row: (int(row["record"]), row["position"], row["type"]))
    for identifier, row in enumerate(rows):
        row["id"] = identifier
    return rows


def _request(model: str, rows: list[dict[str, Any]], seed: int) -> dict[int, tuple[str, float]]:
    exposed = [
        {
            "id": row["id"],
            "text": row["text"],
            "type": row["type"],
            "context": row["context"],
            "model_confidences": row["confidences"],
        }
        for row in rows
    ]
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "format": _SCHEMA,
        "messages": [
            {"role": "system", "content": _PROMPT},
            {"role": "user", "content": json.dumps({"rows": exposed}, ensure_ascii=False)},
        ],
        "options": {"temperature": 0, "seed": seed, "num_ctx": 16384, "num_predict": 2048},
    }
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        body = json.loads(response.read().decode("utf-8"))
    content = body.get("message", {}).get("content", "{}")
    parsed = content if isinstance(content, dict) else json.loads(content)
    return {
        int(item["id"]): (str(item["action"]), float(item.get("confidence", 0)))
        for item in parsed.get("decisions", [])
    }


def review_pair_rows(
    input_dir: str | Path,
    source_dir: str | Path,
    proposal_dirs: list[str | Path],
    output_path: str | Path,
    *,
    model: str = "qwen3:8b",
    batch_size: int = 24,
) -> dict[str, Any]:
    rows = collect_pair_rows(input_dir, source_dir, proposal_dirs)
    decisions = [{}, {}]
    for offset in range(0, len(rows), batch_size):
        batch = rows[offset : offset + batch_size]
        decisions[0].update(_request(model, batch, 1701))
        decisions[1].update(_request(model, batch, 2903))
    accepted = 0
    for row in rows:
        first = decisions[0].get(row["id"], ("DROP", 0.0))
        second = decisions[1].get(row["id"], ("DROP", 0.0))
        row["reviews"] = [
            {"action": first[0], "confidence": first[1]},
            {"action": second[0], "confidence": second[1]},
        ]
        row["accepted"] = (
            first[0] == second[0] == "KEEP" and first[1] >= 0.80 and second[1] >= 0.80
        )
        accepted += int(row["accepted"])
    result = {
        "model": model,
        "seeds": [1701, 2903],
        "eligible": len(rows),
        "accepted": accepted,
        "rows": rows,
    }
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {key: value for key, value in result.items() if key != "rows"}


def merge_pair_review(
    input_dir: str | Path,
    source_dir: str | Path,
    review_path: str | Path,
    output_dir: str | Path,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    inputs, source, output = Path(input_dir), Path(source_dir), Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    review = json.loads(Path(review_path).read_text(encoding="utf-8"))
    accepted_by_record: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in review["rows"]:
        if row.get("accepted"):
            accepted_by_record[row["record"]].append(row)
    from .candidates import CandidateResolver

    diagnoses = CandidateResolver().diagnoses
    counts: Counter[str] = Counter()
    additions: list[dict[str, Any]] = []
    for input_path in sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem)):
        stem = input_path.stem
        raw_text = input_path.read_text(encoding="utf-8")
        baseline = entities_from_json(
            json.loads((source / f"{stem}.json").read_text(encoding="utf-8"))
        )
        new_entities: list[Entity] = []
        for row in accepted_by_record.get(stem, []):
            entity = Entity(
                text=row["text"],
                type=row["type"],
                position=tuple(row["position"]),
                source="pair_qwen",
            )
            entity.assertions = infer_assertions(entity, raw_text)
            if entity.type == "CHẨN_ĐOÁN":
                entity.candidates = list(diagnoses.get(normalize_key(entity.text), ()))[:2]
            new_entities.append(entity)
            counts[entity.type] += 1
            additions.append({**row, "assertions": entity.assertions, "candidates": entity.candidates})
        merged = sorted(baseline + new_entities, key=lambda entity: (entity.position, entity.type))
        validate_entities(merged, raw_text)
        (output / f"{stem}.json").write_text(
            json.dumps([entity.to_dict() for entity in merged], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    report = {
        "source": str(source),
        "review": str(review_path),
        "records": 100,
        "additions": len(additions),
        "additions_by_type": dict(sorted(counts.items())),
        "addition_rows": additions,
    }
    if report_path:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
