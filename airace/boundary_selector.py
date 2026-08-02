"""Constrained local boundary selection for H28."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import urllib.request
from pathlib import Path
from typing import Any, Iterable

from .proposal_pu import DEFAULT_DEV, DEFAULT_TEST


MODEL = "qwen3:8b"
MODEL_ID = "500a1f067a9f"
ALLOWED_TYPES = {
    "CHẨN_ĐOÁN", "TRIỆU_CHỨNG", "TÊN_XÉT_NGHIỆM",
    "KẾT_QUẢ_XÉT_NGHIỆM", "THUỐC",
}
OUTER_PUNCTUATION = " \t\r\n,;:.!?()[]{}\"'“”‘’"
SCHEMA = {
    "type": "object",
    "properties": {
        "decisions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "choice": {"type": "integer"},
                },
                "required": ["id", "choice"],
            },
        }
    },
    "required": ["decisions"],
}
PROMPT = """Bạn chọn BIÊN ĐẦY ĐỦ của một mention y khoa tiếng Việt.
Mỗi hàng có seed được đánh dấu ⟦...⟧, type cố định và danh sách choice là các
substring nguyên văn chứa seed. Chọn đúng một choice_id biểu diễn mention lâm
sàng đầy đủ, tự nhiên và hẹp nhất vẫn đủ nghĩa. Chọn -1 nếu seed không phải
mention đúng type hoặc không choice nào đúng.

Không tự viết/sửa text. Không đổi type. Không chọn cả mệnh đề, nguyên nhân,
thời gian, dấu câu hay từ nối thừa. Giữ modifier thuộc concept (vị trí, mức độ,
tên xét nghiệm, hoạt chất/dạng thuốc) khi cần để mention đầy đủ. Tiền sử, phủ
định, gia đình và đoạn kiến thức không phải lý do loại. Trả đủ một quyết định
cho mỗi id theo schema. /no_think"""


def _trim(raw: str, start: int, end: int) -> tuple[int, int]:
    while start < end and raw[start] in OUTER_PUNCTUATION:
        start += 1
    while end > start and raw[end - 1] in OUTER_PUNCTUATION:
        end -= 1
    return start, end


def enumerate_choices(
    raw: str,
    seed: tuple[int, int],
    *,
    max_tokens: int = 10,
    max_left: int = 4,
    max_right: int = 4,
) -> list[dict[str, Any]]:
    """Enumerate exact, same-line spans containing ``seed``."""
    seed_start, seed_end = seed
    line_start = raw.rfind("\n", 0, seed_start) + 1
    line_end = raw.find("\n", seed_end)
    if line_end < 0:
        line_end = len(raw)
    tokens = [(line_start + match.start(), line_start + match.end())
              for match in re.finditer(r"\S+", raw[line_start:line_end])]
    containing = [index for index, (start, end) in enumerate(tokens)
                  if start <= seed_start and end >= seed_end]
    if not containing:
        # A seed can be only part of a non-space token. Keep it as a safe choice.
        start, end = _trim(raw, seed_start, seed_end)
        return [{"choice_id": 0, "text": raw[start:end], "position": [start, end]}]
    center = containing[0]
    values: dict[tuple[int, int], dict[str, Any]] = {}
    left_min = max(0, center - max_left)
    right_max = min(len(tokens) - 1, center + max_right)
    for left in range(left_min, center + 1):
        for right in range(center, right_max + 1):
            if right - left + 1 > max_tokens:
                continue
            start, end = _trim(raw, tokens[left][0], tokens[right][1])
            if start <= seed_start and end >= seed_end and start < end:
                values[(start, end)] = {
                    "text": raw[start:end], "position": [start, end],
                }
    start, end = _trim(raw, seed_start, seed_end)
    values[(start, end)] = {"text": raw[start:end], "position": [start, end]}
    ordered = sorted(
        values.values(),
        key=lambda item: (
            abs(item["position"][0] - seed_start) + abs(item["position"][1] - seed_end),
            item["position"][1] - item["position"][0],
            item["position"],
        ),
    )
    return [{"choice_id": index, **item} for index, item in enumerate(ordered)]


def _entity_tokens(raw: str, start: int, end: int) -> list[tuple[int, int]]:
    values: list[tuple[int, int]] = []
    for match in re.finditer(r"\S+", raw[start:end]):
        token_start, token_end = _trim(raw, start + match.start(), start + match.end())
        if token_start < token_end:
            values.append((token_start, token_end))
    return values


def _corrupt_seed(record: int, entity: dict[str, Any], tokens: list[tuple[int, int]]) -> tuple[int, int]:
    start, end = entity["position"]
    key = f"{record}:{start}:{end}:{entity['type']}".encode("utf-8")
    return tokens[-1] if hashlib.sha256(key).digest()[0] % 2 else tokens[0]


def build_cases(input_dir: str | Path, target_dir: str | Path,
                records: Iterable[int]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    inputs, targets = Path(input_dir), Path(target_dir)
    cases: list[dict[str, Any]] = []
    eligible = covered = 0
    for record in sorted(records):
        raw = (inputs / f"{record}.txt").read_text(encoding="utf-8")
        entities = json.loads((targets / f"{record}.json").read_text(encoding="utf-8"))
        for entity in entities:
            if entity["type"] not in ALLOWED_TYPES:
                continue
            gold = tuple(entity["position"])
            tokens = _entity_tokens(raw, *gold)
            if not 2 <= len(tokens) <= 8:
                continue
            eligible += 1
            seed = _corrupt_seed(record, entity, tokens)
            choices = enumerate_choices(raw, seed)
            if gold not in {tuple(choice["position"]) for choice in choices}:
                continue
            covered += 1
            line_start = raw.rfind("\n", 0, seed[0]) + 1
            line_end = raw.find("\n", seed[1])
            if line_end < 0:
                line_end = len(raw)
            for mode, active_seed in (("corrupted", seed), ("control", gold)):
                active_choices = enumerate_choices(raw, active_seed)
                if gold not in {tuple(choice["position"]) for choice in active_choices}:
                    continue
                cases.append({
                    "id": len(cases), "record": record, "mode": mode,
                    "type": entity["type"], "seed": list(active_seed),
                    "seed_text": raw[active_seed[0]:active_seed[1]],
                    "gold": list(gold), "gold_text": raw[gold[0]:gold[1]],
                    "context": raw[line_start:active_seed[0]] + "⟦" + raw[active_seed[0]:active_seed[1]] + "⟧" + raw[active_seed[1]:line_end],
                    "choices": active_choices,
                })
    return cases, {"eligible_entities": eligible, "covered_entities": covered,
                   "coverage": covered / eligible if eligible else 1.0}


def _digest(cases: list[dict[str, Any]]) -> str:
    payload = [{key: value for key, value in case.items()
                if key not in {"gold", "gold_text"}} for case in cases]
    return hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _request(rows: list[dict[str, Any]]) -> dict[int, int]:
    exposed = [{
        "id": row["id"], "type": row["type"], "seed": row["seed_text"],
        "context": row["context"],
        "choices": [{"choice_id": choice["choice_id"], "text": choice["text"]}
                    for choice in row["choices"]],
    } for row in rows]
    payload = {
        "model": MODEL, "stream": False, "think": False, "format": SCHEMA,
        "messages": [
            {"role": "system", "content": PROMPT},
            {"role": "user", "content": json.dumps({"rows": exposed}, ensure_ascii=False)},
        ],
        "options": {"temperature": 0, "seed": 4817, "num_ctx": 16384, "num_predict": 2048},
    }
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        body = json.loads(response.read().decode("utf-8"))
    content = body.get("message", {}).get("content", "{}")
    parsed = content if isinstance(content, dict) else json.loads(content)
    return {int(item["id"]): int(item["choice"]) for item in parsed.get("decisions", [])}


def review_cases(cases: list[dict[str, Any]], output_path: str | Path,
                 *, batch_size: int = 10) -> dict[str, Any]:
    target = Path(output_path)
    digest = _digest(cases)
    if target.exists():
        cached = json.loads(target.read_text(encoding="utf-8"))
        if cached.get("case_digest") == digest and cached.get("model_id") == MODEL_ID:
            return cached
    decisions: dict[int, int] = {}
    for offset in range(0, len(cases), batch_size):
        batch = cases[offset:offset + batch_size]
        decisions.update(_request(batch))
        print(f"H28 review {min(offset + batch_size, len(cases))}/{len(cases)}", flush=True)
    reviewed = []
    complete = valid = 0
    for case in cases:
        choice_id = decisions.get(case["id"], -2)
        complete += int(case["id"] in decisions)
        choice = next((item for item in case["choices"] if item["choice_id"] == choice_id), None)
        valid += int(choice_id == -1 or choice is not None)
        reviewed.append({**case, "selected_choice": choice_id,
                         "selected_position": choice["position"] if choice else None,
                         "exact": choice is not None and choice["position"] == case["gold"]})
    artifact = {"model": MODEL, "model_id": MODEL_ID, "case_digest": digest,
                "complete": complete, "valid": valid, "rows": reviewed}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return artifact


def evaluate(review: dict[str, Any], enumeration: dict[str, Any]) -> dict[str, Any]:
    rows = review["rows"]
    corrupted = [row for row in rows if row["mode"] == "corrupted"]
    controls = [row for row in rows if row["mode"] == "control"]
    per_type: dict[str, Any] = {}
    for kind in sorted(ALLOWED_TYPES):
        subset = [row for row in corrupted if row["type"] == kind]
        per_type[kind] = {
            "support": len(subset),
            "exact_recovery": sum(row["exact"] for row in subset) / len(subset) if subset else 1.0,
        }
    return {
        "enumeration": enumeration,
        "corrupted_cases": len(corrupted),
        "corrupted_exact_recovery": sum(row["exact"] for row in corrupted) / len(corrupted) if corrupted else 1.0,
        "control_cases": len(controls),
        "unchanged_control_retention": sum(row["exact"] for row in controls) / len(controls) if controls else 1.0,
        "malformed_response_rate": 1 - review["valid"] / len(rows) if rows else 0.0,
        "responses_complete": review["complete"] == len(rows),
        "per_type": per_type,
    }


def dev_gates(result: dict[str, Any]) -> dict[str, bool]:
    return {
        "enumerator_coverage_at_least_0_95": result["enumeration"]["coverage"] >= 0.95,
        "corrupted_exact_recovery_at_least_0_70": result["corrupted_exact_recovery"] >= 0.70,
        "unchanged_control_retention_at_least_0_93": result["unchanged_control_retention"] >= 0.93,
        "malformed_response_rate_equals_0": result["malformed_response_rate"] == 0,
    }


def test_gates(result: dict[str, Any], first_digest: str, second_digest: str) -> dict[str, bool]:
    supported = [metrics for metrics in result["per_type"].values() if metrics["support"] >= 10]
    return {
        "corrupted_exact_recovery_at_least_0_65": result["corrupted_exact_recovery"] >= 0.65,
        "unchanged_control_retention_at_least_0_90": result["unchanged_control_retention"] >= 0.90,
        "supported_type_recovery_at_least_0_45": all(item["exact_recovery"] >= 0.45 for item in supported),
        "byte_identical_cached_rebuild": first_digest == second_digest,
    }


def run_experiment(input_dir: str | Path, target_dir: str | Path,
                   output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    dev_cases, dev_enumeration = build_cases(input_dir, target_dir, DEFAULT_DEV)
    dev_review = review_cases(dev_cases, output / "dev_review.json")
    dev = evaluate(dev_review, dev_enumeration)
    gates = dev_gates(dev)
    report: dict[str, Any] = {"dev": dev, "dev_gates": gates, "test": None,
                             "test_gates": None, "status": "dev_failed_test_canceled"}
    if all(gates.values()):
        test_cases, test_enumeration = build_cases(input_dir, target_dir, DEFAULT_TEST)
        path = output / "test_review.json"
        test_review = review_cases(test_cases, path)
        first = hashlib.sha256(path.read_bytes()).hexdigest()
        review_cases(test_cases, path)
        second = hashlib.sha256(path.read_bytes()).hexdigest()
        test = evaluate(test_review, test_enumeration)
        final = test_gates(test, first, second)
        report.update({"test": test, "test_gates": final,
                       "status": "passed" if all(final.values()) else "test_failed"})
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="turn2/input")
    parser.add_argument("--target", default="turn2/output_v8_candidate_semantic")
    parser.add_argument("--output", default="experiments/H28_constrained_boundary_selector/results")
    args = parser.parse_args()
    report = run_experiment(args.input, args.target, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
