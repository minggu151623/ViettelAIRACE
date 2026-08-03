"""H57 full-corpus type-specialist Qwen extraction and conservative fusion."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .assertions import infer_assertions
from .multiview_consensus import H34_PATH, VIEW_DIRS, frozen_digest, overlap, relation
from .normalize import normalize_key
from .package_output import package_output
from .phrase_verifier import KNOWN_HAZARDS
from .schema import ASSERTIONS, CANDIDATE_TYPES, ENTITY_TYPES, Entity
from .validator import validate_output_dir


MODEL = "qwen3:8b"
MODEL_ID = "500a1f067a9f"
BASELINE_SHA256 = "a9b9ae07997e57080ed8ce2ad9c390f4cd8c229e8eae8de447f6f47ae6ff4d0b"
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 120
EXPERTS = {
    "clinical": ("CHẨN_ĐOÁN", "TRIỆU_CHỨNG"),
    "laboratory": ("TÊN_XÉT_NGHIỆM", "KẾT_QUẢ_XÉT_NGHIỆM"),
    "medication_patient": ("THUỐC", "THÔNG_TIN_BỆNH_NHÂN"),
}
SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "type": {"type": "string", "enum": sorted(ENTITY_TYPES)},
                    "start": {"type": "integer"},
                    "end": {"type": "integer"},
                    "assertions": {
                        "type": "array",
                        "items": {"type": "string", "enum": sorted(ASSERTIONS)},
                    },
                },
                "required": ["text", "type", "start", "end", "assertions"],
            },
        }
    },
    "required": ["entities"],
}

CHUNK_SCHEMA = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "q": {"type": "string"},
                    "t": {"type": "string", "enum": sorted(ENTITY_TYPES)},
                },
                "required": ["q", "t"],
            },
        }
    },
    "required": ["entities"],
}


def _prompt(name: str) -> str:
    kinds = EXPERTS[name]
    definitions = {
        "clinical": "CHẨN_ĐOÁN là bệnh/hội chứng/tình trạng bệnh lý; TRIỆU_CHỨNG là dấu hiệu, triệu chứng hoặc than phiền.",
        "laboratory": "TÊN_XÉT_NGHIỆM là tên phép đo/xét nghiệm/chẩn đoán hình ảnh; KẾT_QUẢ_XÉT_NGHIỆM là giá trị, đơn vị hoặc kết luận cụ thể của xét nghiệm.",
        "medication_patient": "THUỐC là tên thuốc/hoạt chất/chế phẩm kèm hàm lượng hoặc cách dùng khi có; THÔNG_TIN_BỆNH_NHÂN là tuổi, giới, nghề hay thông tin định danh lâm sàng.",
    }[name]
    return f"""Bạn là chuyên gia NER hồ sơ y khoa tiếng Việt. Chỉ trích xuất hai type: {kinds[0]} và {kinds[1]}.
{definitions}
Quy tắc bắt buộc:
- text phải là nguyên văn liên tục trong hồ sơ, không sửa chính tả hay diễn giải;
- start/end là offset Python [start,end) trong đúng chuỗi đầu vào;
- lấy mention đầy đủ nhưng không nuốt dấu câu, liên từ hay lời giải thích;
- vẫn lấy mention phủ định, tiền sử, gia đình và đoạn kiến thức;
- assertions có thể chứa đồng thời isNegated, isHistorical, isFamily;
- không lấy tiêu đề, giải phẫu đơn thuần, thủ thuật chung hoặc từ quá mơ hồ;
- không trả type ngoài hai type được giao và không tạo ICD/RxNorm.
Trả JSON đúng schema. /no_think"""


def _request(text: str, expert: str, seed: int) -> dict[str, Any]:
    payload = {
        "model": MODEL, "stream": False, "think": False, "format": SCHEMA,
        "messages": [
            {"role": "system", "content": _prompt(expert)},
            {"role": "user", "content": text},
        ],
        "options": {"temperature": 0, "seed": seed, "num_ctx": 8192, "num_predict": 1536},
    }
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=900) as response:
        body = json.loads(response.read().decode("utf-8"))
    value = body.get("message", {}).get("content", "{}")
    return value if isinstance(value, dict) else json.loads(value)


def chunk_windows(raw: str, size: int = CHUNK_SIZE,
                  overlap_size: int = CHUNK_OVERLAP) -> list[tuple[int, int]]:
    """Create deterministic, overlapping windows and prefer natural breaks."""
    if not raw:
        return []
    windows: list[tuple[int, int]] = []
    start = 0
    while start < len(raw):
        hard_end = min(len(raw), start + size)
        end = hard_end
        if hard_end < len(raw):
            floor = start + max(size // 2, size - 300)
            candidates = [raw.rfind(mark, floor, hard_end) for mark in ("\n", ". ", "; ")]
            natural = max(candidates)
            if natural > start:
                end = natural + (1 if raw[natural] == "\n" else 2)
        windows.append((start, end))
        if end == len(raw):
            break
        start = max(start + 1, end - overlap_size)
    return windows


def _chunk_prompt() -> str:
    return """Trích xuất thực thể y khoa từ đúng đoạn tiếng Việt được cung cấp.
Các type hợp lệ: CHẨN_ĐOÁN, TRIỆU_CHỨNG, TÊN_XÉT_NGHIỆM,
KẾT_QUẢ_XÉT_NGHIỆM, THUỐC, THÔNG_TIN_BỆNH_NHÂN.
q phải là nguyên văn liên tục, đầy đủ nhưng không nuốt dấu câu hay liên từ.
Lấy cả mention phủ định, tiền sử, gia đình và kiến thức y khoa. Không lấy tiêu
đề, giải phẫu đơn thuần, thủ thuật chung, nguyên nhân xã hội hay từ mơ hồ.
Chỉ trả JSON gồm q (quote) và t (type); không trả offset, giải thích, assertion
hay mã ICD/RxNorm. /no_think"""


def _request_chunk(text: str, seed: int) -> dict[str, Any]:
    payload = {
        "model": MODEL, "stream": False, "think": False, "format": CHUNK_SCHEMA,
        "messages": [
            {"role": "system", "content": _chunk_prompt()},
            {"role": "user", "content": text},
        ],
        "options": {"temperature": 0, "seed": seed, "num_ctx": 2048,
                    "num_predict": 1024},
    }
    req = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=600) as response:
        body = json.loads(response.read().decode("utf-8"))
    value = body.get("message", {}).get("content", "{}")
    return value if isinstance(value, dict) else json.loads(value)


def normalize_chunk_response(raw: str, start: int, end: int,
                             response: dict[str, Any]) -> list[dict[str, Any]]:
    """Project exact quotes from a window back to raw offsets."""
    chunk = raw[start:end]
    selected: dict[tuple[int, int, str], dict[str, Any]] = {}
    for value in response.get("entities", []):
        quote = str(value.get("q", ""))
        kind = str(value.get("t", ""))
        if kind not in ENTITY_TYPES or not quote.strip() or quote != quote.strip():
            continue
        # Repeated mentions are separate organizer entities. Emit every literal
        # occurrence and let overlap-window de-duplication collapse exact keys.
        for local in _all_occurrences(chunk, quote):
            left, right = start + local, start + local + len(quote)
            key = (left, right, kind)
            selected[key] = {
                "text": raw[left:right], "type": kind,
                "position": [left, right], "assertions": [],
                "source": "qwen_chunk_expert",
            }
    return [selected[key] for key in sorted(selected)]


def _all_occurrences(raw: str, quote: str) -> list[int]:
    if not quote:
        return []
    return [match.start() for match in re.finditer(re.escape(quote), raw)]


def normalize_response(raw: str, expert: str, response: dict[str, Any]) -> list[dict[str, Any]]:
    allowed = set(EXPERTS[expert])
    selected: dict[tuple[int, int, str], dict[str, Any]] = {}
    for value in response.get("entities", []):
        quote, kind = str(value.get("text", "")), str(value.get("type", ""))
        if kind not in allowed or not quote.strip():
            continue
        start, end = int(value.get("start", -1)), int(value.get("end", -1))
        if not (0 <= start < end <= len(raw) and raw[start:end] == quote):
            hits = _all_occurrences(raw, quote)
            if len(hits) != 1:
                continue
            start, end = hits[0], hits[0] + len(quote)
        assertions = [item for item in value.get("assertions", []) if item in ASSERTIONS]
        key = (start, end, kind)
        selected[key] = {"text": raw[start:end], "type": kind,
                         "position": [start, end], "assertions": list(dict.fromkeys(assertions)),
                         "expert": expert, "source": "qwen_section_expert"}
    return [selected[key] for key in sorted(selected)]


def extract_all(input_dir: Path, output_dir: Path) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = output_dir / "_expert_cache"
    cache_dir.mkdir(exist_ok=True)
    counts: Counter[str] = Counter()
    complete = 0
    expected = 0
    for path in sorted(input_dir.glob("*.txt"), key=lambda item: int(item.stem)):
        target = output_dir / f"{path.stem}.json"
        raw = path.read_text(encoding="utf-8")
        windows = chunk_windows(raw)
        expected += len(windows)
        if target.exists():
            cached = json.loads(target.read_text(encoding="utf-8"))
            if cached.get("input_sha256") == hashlib.sha256(raw.encode()).hexdigest() and cached.get("model_id") == MODEL_ID:
                for row in cached.get("entities", []): counts[row["type"]] += 1
                if cached.get("chunks_complete") == len(windows):
                    complete += cached["chunks_complete"]
                    continue
        rows: list[dict[str, Any]] = []
        done = 0
        errors: dict[str, str] = {}
        for index, (left, right) in enumerate(windows):
            try:
                cache_path = cache_dir / f"{path.stem}_chunk_{index}.json"
                input_sha256 = hashlib.sha256(raw.encode()).hexdigest()
                if cache_path.exists():
                    cached_expert = json.loads(cache_path.read_text(encoding="utf-8"))
                else:
                    cached_expert = {}
                if (cached_expert.get("input_sha256") == input_sha256 and
                        cached_expert.get("model_id") == MODEL_ID and
                        cached_expert.get("window") == [left, right]):
                    response = cached_expert["response"]
                else:
                    response = _request_chunk(raw[left:right], 5700 + int(path.stem) * 17 + index)
                    cache_path.write_text(json.dumps({
                        "record": int(path.stem), "chunk": index,
                        "window": [left, right],
                        "model_id": MODEL_ID, "input_sha256": input_sha256,
                        "response": response,
                    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                rows.extend(normalize_chunk_response(raw, left, right, response))
                done += 1
            except Exception as exc:  # fail closed but preserve resumability
                errors[str(index)] = f"{type(exc).__name__}: {exc}"
        unique = {(tuple(row["position"]), row["type"]): row for row in rows}
        entities = [unique[key] for key in sorted(unique)]
        artifact = {"record": int(path.stem), "model": MODEL, "model_id": MODEL_ID,
                    "input_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                    "chunks_expected": len(windows), "chunks_complete": done,
                    "errors": errors, "entities": entities}
        target.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for row in entities: counts[row["type"]] += 1
        complete += done
        print(f"H57 extract {path.stem}/100 chunks={done}/{len(windows)} entities={len(entities)}", flush=True)
    return {"records": 100, "chunk_calls_expected": expected,
            "chunk_calls_complete": complete, "counts": dict(counts),
            "proposal_digest": frozen_digest(output_dir)}


def _neural_support() -> dict[tuple[int, int, int, str], set[str]]:
    support: dict[tuple[int, int, int, str], set[str]] = defaultdict(set)
    for name, root in VIEW_DIRS.items():
        family = "bami" if name.startswith("bami_") else name
        if name == "qwen_guarded":
            continue
        for path in root.glob("*.json"):
            record = int(path.stem)
            for row in json.loads(path.read_text(encoding="utf-8")):
                support[(record, *map(int, row["position"]), str(row["type"]))].add(family)
    for row in json.loads(H34_PATH.read_text(encoding="utf-8")):
        support[(int(row["record"]), *map(int, row["position"]), str(row["type"]))].add("h34_oof")
    return support


def _load_records(root: Path) -> dict[int, list[dict[str, Any]]]:
    return {int(path.stem): json.loads(path.read_text(encoding="utf-8"))
            for path in root.glob("*.json")}


def _aliases(records: dict[int, list[dict[str, Any]]]) -> dict[tuple[str, str], set[tuple[str, ...]]]:
    values: dict[tuple[str, str], set[tuple[str, ...]]] = defaultdict(set)
    for rows in records.values():
        for row in rows:
            if row["type"] in CANDIDATE_TYPES and row.get("candidates"):
                values[(row["type"], normalize_key(row["text"]))].add(tuple(row["candidates"]))
    return values


def _hazard(row: dict[str, Any]) -> bool:
    text = row["text"].strip()
    return (normalize_key(text) in KNOWN_HAZARDS or
            (row["type"] == "TRIỆU_CHỨNG" and text[:1].isdigit() and
             not any(char.isalpha() for char in text.replace("°C", ""))))


def merge(input_dir: Path, baseline_dir: Path, baseline_zip: Path, proposals: Path,
          output_dir: Path, zip_path: Path) -> dict[str, Any]:
    observed = hashlib.sha256(baseline_zip.read_bytes()).hexdigest()
    if observed != BASELINE_SHA256:
        raise ValueError(f"H57 baseline hash mismatch: {observed}")
    baseline = _load_records(baseline_dir)
    aliases = _aliases(baseline)
    neural = _neural_support()
    selected: list[dict[str, Any]] = []
    rejected: Counter[str] = Counter()
    for path in sorted(proposals.glob("*.json"), key=lambda item: int(item.stem)):
        artifact = json.loads(path.read_text(encoding="utf-8"))
        if artifact.get("chunks_complete") != artifact.get("chunks_expected"):
            rejected["incomplete_experts"] += len(artifact.get("entities", []))
            continue
        record = int(path.stem)
        raw = (input_dir / f"{record}.txt").read_text(encoding="utf-8")
        for row in artifact["entities"]:
            key = (record, *map(int, row["position"]), row["type"])
            if not neural.get(key):
                rejected["no_independent_exact_support"] += 1
                continue
            if _hazard(row):
                rejected["hazard"] += 1
                continue
            rel, hits = relation(row, baseline[record])
            if rel != "disjoint":
                rejected[rel] += 1
                continue
            value = {"record": record, **row, "relation": rel,
                     "baseline_overlap_indices": hits,
                     "independent_sources": sorted(neural[key])}
            if rel == "disjoint" and row["type"] in CANDIDATE_TYPES:
                tuples = aliases.get((row["type"], normalize_key(row["text"])), set())
                if len(tuples) != 1:
                    rejected["candidate_alias_not_unanimous"] += 1
                    continue
                value["candidates"] = list(next(iter(tuples)))
            selected.append(value)

    # Resolve overlaps among new rows, favoring more independent sources then longer span.
    kept: list[dict[str, Any]] = []
    for row in sorted(selected, key=lambda x: (-len(x["independent_sources"]),
                      -(x["position"][1] - x["position"][0]), x["record"],
                      x["position"][0], x["type"])):
        if any(row["record"] == old["record"] and
               overlap(tuple(row["position"]), tuple(old["position"])) for old in kept):
            rejected["new_overlap"] += 1
            continue
        kept.append(row)
    kept.sort(key=lambda x: (x["record"], *x["position"], x["type"]))

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    changes = 0
    candidate_additions = 0
    by_record: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in kept: by_record[row["record"]].append(row)
    for record in range(1, 101):
        raw = (input_dir / f"{record}.txt").read_text(encoding="utf-8")
        rows = [dict(row) for row in baseline[record]]
        remove: set[int] = set()
        additions: list[dict[str, Any]] = []
        for proposal in by_record[record]:
            hits = proposal["baseline_overlap_indices"]
            if proposal["relation"] == "contained_same_type":
                remove.update(hits)
                assertions = list(dict.fromkeys(item for i in hits for item in rows[i].get("assertions", [])))
                candidates = list(dict.fromkeys(item for i in hits for item in rows[i].get("candidates", [])))
            else:
                rule = list(infer_assertions(
                    Entity(text=proposal["text"], type=proposal["type"],
                           position=tuple(proposal["position"])), raw))
                assertions = rule
                candidates = proposal.get("candidates", [])
            entity = Entity(text=proposal["text"], type=proposal["type"], assertions=assertions,
                            position=tuple(proposal["position"]),
                            candidates=candidates if proposal["type"] in CANDIDATE_TYPES else None)
            additions.append(entity.to_dict())
            candidate_additions += int(proposal["relation"] == "disjoint" and bool(candidates))
        merged = [row for index, row in enumerate(rows) if index not in remove] + additions
        merged.sort(key=lambda row: (*row["position"], row["type"], row["text"]))
        changes += len(remove) + len(additions)
        (output_dir / f"{record}.json").write_text(
            json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    validation = validate_output_dir(input_dir, output_dir, position_mode="raw")
    baseline_keys = {
        (record, *map(int, row["position"]), row["type"])
        for record, rows in baseline.items() for row in rows
    }
    output_records = _load_records(output_dir)
    output_keys = {
        (record, *map(int, row["position"]), row["type"])
        for record, rows in output_records.items() for row in rows
    }
    retention = len(baseline_keys & output_keys) / max(1, len(baseline_keys))
    gates = {
        "baseline_hash_matches": True,
        "all_chunk_calls_complete": all(
            json.loads(path.read_text())["chunks_complete"] ==
            json.loads(path.read_text())["chunks_expected"]
            for path in proposals.glob("*.json")),
        "all_selected_have_independent_support": all(row["independent_sources"] for row in kept),
        "positive_control_retention_at_least_0_90": retention >= 0.90,
        "at_least_150_rows_change": changes >= 150,
        "candidate_count_increase_at_most_75": candidate_additions <= 75,
        "all_records_validate": validation["ok"],
    }
    report = {"hypothesis": "H57_section_expert_core", "proposal_digest": frozen_digest(proposals),
              "selected": len(kept), "changed_rows": changes,
              "baseline_retention": retention,
              "candidate_additions": candidate_additions, "rejected": dict(rejected),
              "selected_by_type": dict(Counter(row["type"] for row in kept)),
              "selected_rows": kept, "validation": validation, "gates": gates,
              "decision": "PASS" if all(gates.values()) else "FAIL"}
    if report["decision"] == "PASS":
        package_output(output_dir, zip_path)
        report["zip_sha256"] = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        repeat_zip = zip_path.with_name(zip_path.stem + "_repeat.zip")
        package_output(output_dir, repeat_zip)
        report["repeat_zip_sha256"] = hashlib.sha256(repeat_zip.read_bytes()).hexdigest()
        report["byte_identical_repeat"] = zip_path.read_bytes() == repeat_zip.read_bytes()
        repeat_zip.unlink()
        if not report["byte_identical_repeat"]:
            zip_path.unlink()
            report["decision"] = "FAIL"
            report["gates"]["repeated_merge_and_zip_byte_identical"] = False
        else:
            report["gates"]["repeated_merge_and_zip_byte_identical"] = True
    elif zip_path.exists():
        zip_path.unlink()
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    extract = sub.add_parser("extract")
    extract.add_argument("--input", type=Path, default=Path("turn2/input"))
    extract.add_argument("--output", type=Path, default=Path("experiments/H57_section_expert_core/proposals"))
    fuse = sub.add_parser("merge")
    fuse.add_argument("--input", type=Path, default=Path("turn2/input"))
    fuse.add_argument("--baseline", type=Path, default=Path("turn2/output_v10_multiview_consensus"))
    fuse.add_argument("--baseline-zip", type=Path, default=Path("turn2/output_v10_multiview_consensus.zip"))
    fuse.add_argument("--proposals", type=Path, default=Path("experiments/H57_section_expert_core/proposals"))
    fuse.add_argument("--output", type=Path, default=Path("turn2/output_v13_section_expert_core"))
    fuse.add_argument("--zip", type=Path, default=Path("turn2/output_v13_section_expert_core.zip"))
    fuse.add_argument("--report", type=Path, default=Path("experiments/H57_section_expert_core/results/report.json"))
    args = parser.parse_args()
    if args.command == "extract":
        report = extract_all(args.input, args.output)
    else:
        report = merge(args.input, args.baseline, args.baseline_zip, args.proposals, args.output, args.zip)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
