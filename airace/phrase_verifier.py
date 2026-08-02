"""Dual-prompt local-LLM verification for fixed H26 phrase candidates."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from pathlib import Path
from typing import Any, Iterable

from .normalize import normalize_key
from .phrase_policy import (
    PhraseProposal,
    build_lexicon,
    match_lexicon,
    select_disjoint,
)
from .proposal_pu import DEFAULT_DEV, DEFAULT_TEST, DEFAULT_TRAIN, TYPE_ORDER, _entity_key, _prf


MODEL = "qwen3:8b"
MODEL_ID = "500a1f067a9f"
REASONS = (
    "clinical_exact", "wrong_type", "incomplete_boundary", "homonym_nonclinical",
    "generic_word", "heading", "other",
)
SCHEMA = {
    "type": "object",
    "properties": {
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "action": {"type": "string", "enum": ["KEEP", "DROP"]},
                    "reason": {"type": "string", "enum": list(REASONS)},
                },
                "required": ["id", "action", "reason"],
            },
        }
    },
    "required": ["decisions"],
}
SEMANTIC_PROMPT = """Bạn là bác sĩ kiểm định một candidate NER cố định trong hồ sơ y khoa tiếng Việt.
Không tạo hoặc sửa span. Chỉ KEEP/DROP candidate được đánh dấu ⟦...⟧.

KEEP khi đúng toàn bộ hai điều:
1) cụm được đánh dấu là một khái niệm lâm sàng rõ ràng trong chính ngữ cảnh;
2) đúng type đề xuất theo taxonomy:
- CHẨN_ĐOÁN: bệnh, hội chứng, tình trạng bệnh lý;
- TRIỆU_CHỨNG: triệu chứng, dấu hiệu, than phiền;
- THUỐC: tên thuốc/hoạt chất/chế phẩm cụ thể, không phải nhóm chung;
- TÊN_XÉT_NGHIỆM: tên phép đo, xét nghiệm hoặc chẩn đoán hình ảnh;
- KẾT_QUẢ_XÉT_NGHIỆM: giá trị/kết luận của một xét nghiệm cụ thể.

Mention trong tiền sử, phủ định, gia đình hoặc đoạn kiến thức vẫn KEEP nếu nó
thực sự là concept đúng type. DROP từ thông thường, giải phẫu đơn thuần, type
sai, nhóm thuốc chung hoặc kết quả không gắn với xét nghiệm. Trả đủ một quyết
định cho mỗi id theo schema. Không dùng confidence. /no_think"""
BOUNDARY_PROMPT = """Bạn kiểm định BIÊN của candidate NER tiếng Việt được đánh dấu ⟦...⟧.
Không tạo hoặc sửa span. Chỉ KEEP/DROP.

KEEP khi phần trong ngoặc là một mention hoàn chỉnh và đúng nghĩa trong câu.
DROP khi là:
- mảnh cụt của cụm dài hơn (ví dụ `phù` trong `phù hợp`, `đau` trong `đỡ đau` nếu policy cần cụm đầy đủ);
- từ đồng âm/đa nghĩa không mang nghĩa lâm sàng (`mạch` trong `mạch máu` không phải tên xét nghiệm);
- token bị dính do lỗi (`doxycyclinebactrim`, `ảo giácxuất`);
- tiêu đề/từ quá chung (`thuốc`, `đoạn`, `buồn`);
- ranh giới hoặc type rõ ràng sai.

Phủ định, tiền sử, gia đình, lặp lại và đoạn kiến thức không phải lý do DROP nếu
mention vẫn hoàn chỉnh. Trả đủ một quyết định mỗi id theo schema. /no_think"""
KNOWN_HAZARDS = {
    normalize_key(value) for value in (
        "doxycyclinebactrim", "klonopinclonidine", "ảo giácxuất", "buồn", "đoạn"
    )
}


def _load_entities(root: Path, record: int) -> list[dict[str, Any]]:
    return json.loads((root / f"{record}.json").read_text(encoding="utf-8"))


def collect_candidates(
    input_dir: str | Path,
    h23_dir: str | Path,
    h20_dir: str | Path,
    records: Iterable[int],
) -> list[dict[str, Any]]:
    inputs, h23, h20 = Path(input_dir), Path(h23_dir), Path(h20_dir)
    lexicon = build_lexicon(h23, DEFAULT_TRAIN, 2)
    rows: list[dict[str, Any]] = []
    for record in sorted(records):
        raw = (inputs / f"{record}.txt").read_text(encoding="utf-8")
        baseline = _load_entities(h20, record)
        gold = {_entity_key(value) for value in _load_entities(h23, record)}
        matches = match_lexicon(raw, record, lexicon, case_sensitive=False)
        selected = select_disjoint(matches, [tuple(value["position"]) for value in baseline])
        for proposal in selected:
            start, end = proposal.position
            rows.append({
                "id": len(rows),
                "record": record,
                "text": proposal.text,
                "type": proposal.type,
                "position": [start, end],
                "record_support": proposal.record_support,
                "context": raw[max(0, start - 180):start] + "⟦" + raw[start:end] + "⟧" + raw[end:min(len(raw), end + 180)],
                "pseudo_positive": proposal.key in gold,
            })
    return rows


def _candidate_digest(rows: list[dict[str, Any]]) -> str:
    exposed = [{key: value for key, value in row.items() if key != "pseudo_positive"} for row in rows]
    payload = json.dumps(exposed, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _request(rows: list[dict[str, Any]], prompt: str, seed: int) -> dict[int, dict[str, str]]:
    exposed = [{
        "id": row["id"], "text": row["text"], "type": row["type"],
        "record_support": row["record_support"], "context": row["context"],
    } for row in rows]
    payload = {
        "model": MODEL,
        "stream": False,
        "think": False,
        "format": SCHEMA,
        "messages": [
            {"role": "system", "content": prompt},
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
        int(item["id"]): {"action": str(item["action"]), "reason": str(item["reason"])}
        for item in parsed.get("decisions", [])
    }


def review_candidates(
    rows: list[dict[str, Any]],
    output_path: str | Path,
    *,
    batch_size: int = 18,
) -> dict[str, Any]:
    target = Path(output_path)
    digest = _candidate_digest(rows)
    if target.exists():
        cached = json.loads(target.read_text(encoding="utf-8"))
        if cached.get("candidate_digest") == digest and cached.get("model_id") == MODEL_ID:
            return cached
    semantic: dict[int, dict[str, str]] = {}
    boundary: dict[int, dict[str, str]] = {}
    for offset in range(0, len(rows), batch_size):
        batch = rows[offset:offset + batch_size]
        semantic.update(_request(batch, SEMANTIC_PROMPT, 3109))
        boundary.update(_request(batch, BOUNDARY_PROMPT, 7823))
        print(f"H27 review {min(offset + batch_size, len(rows))}/{len(rows)}", flush=True)
    reviewed: list[dict[str, Any]] = []
    complete = 0
    for row in rows:
        left = semantic.get(row["id"], {"action": "DROP", "reason": "other"})
        right = boundary.get(row["id"], {"action": "DROP", "reason": "other"})
        present = row["id"] in semantic and row["id"] in boundary
        complete += int(present)
        reviewed.append({
            **row,
            "semantic": left,
            "boundary": right,
            "accepted": present and left["action"] == right["action"] == "KEEP",
        })
    artifact = {
        "model": MODEL,
        "model_id": MODEL_ID,
        "candidate_digest": digest,
        "complete": complete,
        "eligible": len(rows),
        "rows": reviewed,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return artifact


def evaluate_review(
    review: dict[str, Any],
    h23_dir: str | Path,
    h20_dir: str | Path,
    records: set[int],
) -> dict[str, Any]:
    h23, h20 = Path(h23_dir), Path(h20_dir)
    baseline: set[tuple[int, int, str, int]] = set()
    gold: set[tuple[int, int, str, int]] = set()
    raw: set[tuple[int, int, str, int]] = set()
    accepted: set[tuple[int, int, str, int]] = set()
    true_raw = true_accepted = 0
    hazards: list[dict[str, Any]] = []
    for record in records:
        baseline.update((*_entity_key(value), record) for value in _load_entities(h20, record))
        gold.update((*_entity_key(value), record) for value in _load_entities(h23, record))
    for row in review["rows"]:
        key = (int(row["position"][0]), int(row["position"][1]), row["type"], int(row["record"]))
        raw.add(key)
        true_raw += int(bool(row["pseudo_positive"]))
        if row["accepted"]:
            accepted.add(key)
            true_accepted += int(bool(row["pseudo_positive"]))
        if normalize_key(row["text"]) in KNOWN_HAZARDS:
            hazards.append({"record": row["record"], "text": row["text"], "accepted": row["accepted"]})
    predicted = baseline | accepted
    raw_precision = _prf(raw, gold - baseline)["precision"]
    accepted_metrics = _prf(accepted, gold - baseline)
    per_type: dict[str, Any] = {}
    for kind in TYPE_ORDER:
        b = {key for key in baseline if key[2] == kind}
        p = {key for key in predicted if key[2] == kind}
        g = {key for key in gold if key[2] == kind}
        per_type[kind] = {"baseline": _prf(b, g), "with_additions": _prf(p, g)}
    return {
        "eligible": len(raw),
        "accepted": len(accepted),
        "raw_true_additions": true_raw,
        "accepted_true_additions": true_accepted,
        "true_addition_retention": true_accepted / true_raw if true_raw else 1.0,
        "raw_pseudo_precision": raw_precision,
        "accepted_additions": accepted_metrics,
        "pseudo_precision_gain": accepted_metrics["precision"] - raw_precision,
        "baseline": _prf(baseline, gold),
        "with_additions": _prf(predicted, gold),
        "per_type": per_type,
        "known_hazards": hazards,
        "all_known_hazards_dropped": all(not row["accepted"] for row in hazards),
        "responses_complete": review["complete"] == review["eligible"],
    }


def _split_gates(result: dict[str, Any]) -> dict[str, bool]:
    f1_gain = 100 * (result["with_additions"]["f1"] - result["baseline"]["f1"])
    return {
        "true_retention_at_least_0_80": result["true_addition_retention"] >= 0.80,
        "precision_gain_at_least_0_15": result["pseudo_precision_gain"] >= 0.15,
        "strict_f1_gain_at_least_3": f1_gain >= 3,
    }


def run_experiment(
    input_dir: str | Path,
    h23_dir: str | Path,
    h20_dir: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    dev_rows = collect_candidates(input_dir, h23_dir, h20_dir, DEFAULT_DEV)
    dev_review = review_candidates(dev_rows, target / "dev_review.json")
    dev = evaluate_review(dev_review, h23_dir, h20_dir, set(DEFAULT_DEV))
    dev_gates = _split_gates(dev)
    report: dict[str, Any] = {
        "label_warning": "H23 absence remains unlabeled; pseudo precision is only a diagnostic.",
        "dev": dev,
        "dev_gates": dev_gates,
        "test": None,
        "test_gates": None,
        "status": "dev_failed_test_canceled",
    }
    if all(dev_gates.values()):
        test_rows = collect_candidates(input_dir, h23_dir, h20_dir, DEFAULT_TEST)
        test_review = review_candidates(test_rows, target / "test_review.json")
        test = evaluate_review(test_review, h23_dir, h20_dir, set(DEFAULT_TEST))
        test_gates = _split_gates(test)
        type_losses = [
            100 * (metrics["with_additions"]["f1"] - metrics["baseline"]["f1"])
            for metrics in test["per_type"].values()
        ]
        final = {
            **test_gates,
            "no_type_loses_more_than_2": min(type_losses, default=0) >= -2,
            "known_hazards_dropped": test["all_known_hazards_dropped"],
            "responses_complete": test["responses_complete"],
        }
        report.update({
            "test": test,
            "test_gates": final,
            "status": "passed" if all(final.values()) else "test_failed",
        })
    (target / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="turn2/input")
    parser.add_argument("--h23", default="turn2/output_v8_candidate_semantic")
    parser.add_argument("--h20", default="turn2/output_v6_expanded_pair")
    parser.add_argument("--output", default="experiments/H27_phrase_context_verifier/results")
    args = parser.parse_args()
    report = run_experiment(args.input, args.h23, args.h20, args.output)
    print(json.dumps({"status": report["status"], "dev": report["dev"],
                      "dev_gates": report["dev_gates"], "test": report["test"],
                      "test_gates": report["test_gates"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
