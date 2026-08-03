"""H62: two-stage LLM assertion classification over frozen H38 entities."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

from .package_output import package_output
from .schema import ASSERTIONS
from .section_expert_core import BASELINE_SHA256, _load_records
from .validator import validate_output_dir


MODEL = "qwen3:8b"
MODEL_ID = "500a1f067a9f"
ELIGIBLE_TYPES = {"CHẨN_ĐOÁN", "TRIỆU_CHỨNG", "THUỐC"}
REMOVAL_CATEGORIES = {
    "pseudo_trigger",
    "outside_scope",
    "current_or_active",
    "patient_is_subject",
    "lexical_negation_inside_positive_symptom",
    "other_explicit",
}

DIRECT_SCHEMA = {
    "type": "object",
    "properties": {
        "labels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "assertions": {
                        "type": "array",
                        "items": {"type": "string", "enum": sorted(ASSERTIONS)},
                    },
                },
                "required": ["id", "assertions"],
            },
        }
    },
    "required": ["labels"],
}

CRITIC_SCHEMA = {
    "type": "object",
    "properties": {
        "reviews": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "assertions": {
                        "type": "array",
                        "items": {"type": "string", "enum": sorted(ASSERTIONS)},
                    },
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string", "enum": sorted(ASSERTIONS)},
                                "quote": {"type": "string"},
                            },
                            "required": ["label", "quote"],
                        },
                    },
                    "removals": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "label": {"type": "string", "enum": sorted(ASSERTIONS)},
                                "category": {
                                    "type": "string",
                                    "enum": sorted(REMOVAL_CATEGORIES),
                                },
                            },
                            "required": ["label", "category"],
                        },
                    },
                },
                "required": ["id", "assertions", "evidence", "removals"],
            },
        }
    },
    "required": ["reviews"],
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request(system: str, user: str, schema: dict[str, Any], seed: int) -> dict[str, Any]:
    payload = {
        "model": MODEL,
        "stream": False,
        "think": False,
        "format": schema,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "options": {
            "temperature": 0,
            "seed": seed,
            "num_ctx": 8192,
            "num_predict": 3072,
        },
    }
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=900) as response:
        body = json.loads(response.read().decode("utf-8"))
    value = body.get("message", {}).get("content", "{}")
    return value if isinstance(value, dict) else json.loads(value)


def _entities_for_prompt(rows: list[dict[str, Any]], *, include_current: bool) -> list[dict[str, Any]]:
    values = []
    for index, row in enumerate(rows):
        if row["type"] not in ELIGIBLE_TYPES:
            continue
        value: dict[str, Any] = {
            "id": index,
            "text": row["text"],
            "type": row["type"],
            "position": row["position"],
        }
        if include_current:
            value["current_assertions"] = row.get("assertions") or []
        values.append(value)
    return values


def _direct_prompt() -> str:
    return """Bạn phân loại assertion cho từng thực thể y khoa đã được đánh dấu trong hồ sơ tiếng Việt.
Chỉ dùng ba nhãn, có thể đa nhãn:
- isNegated: chính bệnh/triệu chứng/thuốc bị phủ nhận, loại trừ hoặc nói là không hiện diện.
- isHistorical: mention thuộc tiền sử/sự kiện hay thuốc trong quá khứ, không phải tình trạng hiện tại. Bệnh mạn đang hoạt động hoặc 'bệnh sử hiện tại' không tự động là lịch sử.
- isFamily: tình trạng thuộc người thân của chủ thể bệnh nhân. Người kể có thể là cha/mẹ/bạn, nhưng đứa trẻ/người bạn đang được hỏi khám vẫn là chủ thể bệnh nhân, không phải family.
Chú ý pseudo-trigger và scope: 'không thể đi lại' là triệu chứng dương tính về mất khả năng, không phải phủ nhận; 'không đặc hiệu/không do' không phủ nhận bệnh; dấu chấm, xuống dòng, 'nhưng/tuy nhiên' kết thúc scope. Phân loại mọi id đúng một lần. Không sửa entity. Chỉ trả JSON. /no_think"""


def _critic_prompt() -> str:
    return """Bạn là bác sĩ phản biện assertion, đánh giá độc lập từng disagreement trong hồ sơ.
Định nghĩa: isNegated chỉ khi chính mention bị phủ nhận/loại trừ; isHistorical chỉ khi mention thực sự ở quá khứ/tiền sử chứ không phải bệnh mạn hiện hoạt hay bệnh sử hiện tại; isFamily chỉ khi tình trạng thuộc người thân của chủ thể được khám, không phải chỉ vì người thân là người kể.
Với mỗi id, trả final assertions. Mỗi nhãn dương phải có một evidence quote nguyên văn trong hồ sơ. Mỗi nhãn current_assertions bị loại phải có removal category: pseudo_trigger, outside_scope, current_or_active, patient_is_subject, lexical_negation_inside_positive_symptom, hoặc other_explicit. Không dựa vào thống kê toàn bộ, leaderboard hay đề xuất của pass khác. Chỉ trả JSON. /no_think"""


def _write_cache(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def direct_pass(input_dir: Path, baseline_dir: Path, output_dir: Path) -> dict[str, Any]:
    baseline = _load_records(baseline_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    expected = returned = malformed = 0
    for record in range(1, 101):
        raw = (input_dir / f"{record}.txt").read_text(encoding="utf-8")
        entities = _entities_for_prompt(baseline[record], include_current=False)
        expected += len(entities)
        target = output_dir / f"{record}.json"
        input_hash = hashlib.sha256(
            (raw + json.dumps(entities, ensure_ascii=False, sort_keys=True)).encode()
        ).hexdigest()
        cached = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
        if cached.get("input_sha256") == input_hash and cached.get("model_id") == MODEL_ID:
            response = cached["response"]
        else:
            user = json.dumps({"record": record, "document": raw, "entities": entities}, ensure_ascii=False)
            response = _request(_direct_prompt(), user, DIRECT_SCHEMA, 62000 + record)
            _write_cache(target, {"record": record, "model_id": MODEL_ID,
                                  "input_sha256": input_hash, "response": response})
        valid_ids = {item["id"] for item in entities}
        seen: set[int] = set()
        for item in response.get("labels", []):
            item_id = item.get("id")
            labels = item.get("assertions")
            if (not isinstance(item_id, int) or item_id not in valid_ids or item_id in seen
                    or not isinstance(labels, list) or any(label not in ASSERTIONS for label in labels)):
                malformed += 1
                continue
            seen.add(item_id)
        returned += len(seen)
        print(json.dumps({"stage": "direct", "record": record,
                          "expected": len(entities), "returned": len(seen)}), flush=True)
    return {"expected": expected, "returned": returned, "malformed": malformed,
            "missing": expected - returned,
            "missing_rate": (expected - returned) / expected if expected else 0.0}


def _load_direct(path: Path) -> dict[int, tuple[str, ...]]:
    payload = json.loads(path.read_text(encoding="utf-8"))["response"]
    out: dict[int, tuple[str, ...]] = {}
    for item in payload.get("labels", []):
        item_id, labels = item.get("id"), item.get("assertions")
        if (isinstance(item_id, int) and item_id not in out and isinstance(labels, list)
                and all(label in ASSERTIONS for label in labels)):
            out[item_id] = tuple(dict.fromkeys(labels))
    return out


def critic_pass(input_dir: Path, baseline_dir: Path, direct_dir: Path,
                output_dir: Path, start_record: int = 1,
                end_record: int = 100) -> dict[str, Any]:
    baseline = _load_records(baseline_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    disagreements = returned = malformed = 0
    for record in range(start_record, end_record + 1):
        raw = (input_dir / f"{record}.txt").read_text(encoding="utf-8")
        direct = _load_direct(direct_dir / f"{record}.json")
        items = []
        for index, row in enumerate(baseline[record]):
            if row["type"] not in ELIGIBLE_TYPES or index not in direct:
                continue
            current = tuple(row.get("assertions") or [])
            if set(current) == set(direct[index]):
                continue
            items.append({
                "id": index, "text": row["text"], "type": row["type"],
                "position": row["position"], "current_assertions": list(current),
            })
        disagreements += len(items)
        legacy_target = output_dir / f"{record}.json"
        input_hash = hashlib.sha256(
            (raw + json.dumps(items, ensure_ascii=False, sort_keys=True)).encode()
        ).hexdigest()
        if not items:
            _write_cache(legacy_target, {"record": record, "model_id": MODEL_ID,
                                        "input_sha256": input_hash, "response": {"reviews": []}})
            continue
        valid_ids = {item["id"] for item in items}
        seen: set[int] = set()
        legacy = (json.loads(legacy_target.read_text(encoding="utf-8"))
                  if legacy_target.exists() else {})
        if legacy.get("input_sha256") == input_hash and legacy.get("model_id") == MODEL_ID:
            responses = [legacy["response"]]
        else:
            responses = []
            # Long evidence-rich critic responses can exceed the structured
            # generation budget. Batching changes only transport/runtime, not
            # the frozen prompt, decision rule, or per-row evidence contract.
            for batch_index, start in enumerate(range(0, len(items), 10)):
                batch = items[start:start + 10]
                target = output_dir / f"{record}_{batch_index}.json"
                batch_hash = hashlib.sha256(
                    (raw + json.dumps(batch, ensure_ascii=False, sort_keys=True)).encode()
                ).hexdigest()
                cached = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
                if cached.get("input_sha256") == batch_hash and cached.get("model_id") == MODEL_ID:
                    response = cached["response"]
                else:
                    user = json.dumps({"record": record, "document": raw,
                                       "entities_to_review": batch}, ensure_ascii=False)
                    response = _request(
                        _critic_prompt(), user, CRITIC_SCHEMA,
                        72000 + record * 17 + batch_index,
                    )
                    _write_cache(target, {"record": record, "batch": batch_index,
                                          "model_id": MODEL_ID,
                                          "input_sha256": batch_hash,
                                          "response": response})
                responses.append(response)
        for response in responses:
            for item in response.get("reviews", []):
                item_id = item.get("id")
                labels = item.get("assertions")
                if (not isinstance(item_id, int) or item_id not in valid_ids or item_id in seen
                        or not isinstance(labels, list)
                        or any(label not in ASSERTIONS for label in labels)):
                    malformed += 1
                    continue
                seen.add(item_id)
        returned += len(seen)
        print(json.dumps({"stage": "critic", "record": record,
                          "expected": len(items), "returned": len(seen)}), flush=True)
    return {"disagreements": disagreements, "returned": returned, "malformed": malformed,
            "missing": disagreements - returned,
            "missing_rate": (disagreements - returned) / disagreements if disagreements else 0.0}


def _load_reviews(path: Path) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    paths = [path] if path.exists() else sorted(
        path.parent.glob(f"{path.stem}_*.json"),
        key=lambda item: int(item.stem.rsplit("_", 1)[1]),
    )
    for source in paths:
        payload = json.loads(source.read_text(encoding="utf-8"))["response"]
        for item in payload.get("reviews", []):
            item_id = item.get("id")
            if isinstance(item_id, int) and item_id not in out:
                out[item_id] = item
    return out


def _response_audit(
    rows: list[dict[str, Any]],
    direct_path: Path,
    critic_path: Path,
) -> dict[str, int]:
    """Recount cached response coverage without trusting CLI run summaries."""
    eligible_ids = {
        index for index, row in enumerate(rows) if row["type"] in ELIGIBLE_TYPES
    }
    direct_payload = json.loads(direct_path.read_text(encoding="utf-8"))["response"]
    direct_seen: set[int] = set()
    direct_malformed = 0
    for item in direct_payload.get("labels", []):
        item_id, labels = item.get("id"), item.get("assertions")
        if (
            not isinstance(item_id, int)
            or item_id not in eligible_ids
            or item_id in direct_seen
            or not isinstance(labels, list)
            or any(label not in ASSERTIONS for label in labels)
        ):
            direct_malformed += 1
            continue
        direct_seen.add(item_id)

    direct = _load_direct(direct_path)
    disagreement_ids = {
        index
        for index, row in enumerate(rows)
        if index in direct
        and set(row.get("assertions") or []) != set(direct[index])
    }
    review_seen: set[int] = set()
    critic_malformed = 0
    paths = [critic_path] if critic_path.exists() else sorted(
        critic_path.parent.glob(f"{critic_path.stem}_*.json"),
        key=lambda item: int(item.stem.rsplit("_", 1)[1]),
    )
    for source in paths:
        payload = json.loads(source.read_text(encoding="utf-8"))["response"]
        for item in payload.get("reviews", []):
            item_id, labels = item.get("id"), item.get("assertions")
            if (
                not isinstance(item_id, int)
                or item_id not in disagreement_ids
                or item_id in review_seen
                or not isinstance(labels, list)
                or any(label not in ASSERTIONS for label in labels)
            ):
                critic_malformed += 1
                continue
            review_seen.add(item_id)
    return {
        "direct_expected": len(eligible_ids),
        "direct_returned": len(direct_seen),
        "direct_missing": len(eligible_ids - direct_seen),
        "direct_malformed": direct_malformed,
        "critic_expected": len(disagreement_ids),
        "critic_returned": len(review_seen),
        "critic_missing": len(disagreement_ids - review_seen),
        "critic_malformed": critic_malformed,
    }


def build(input_dir: Path, baseline_dir: Path, baseline_zip: Path,
          direct_dir: Path, critic_dir: Path, output_dir: Path,
          zip_path: Path) -> dict[str, Any]:
    baseline_hash = _sha256(baseline_zip)
    if baseline_hash != BASELINE_SHA256:
        raise ValueError(f"H62 baseline hash mismatch: {baseline_hash}")
    baseline = _load_records(baseline_dir)
    changes: list[dict[str, Any]] = []
    invalid = Counter()
    response_audit = Counter()
    final: dict[int, list[dict[str, Any]]] = {}
    for record in range(1, 101):
        raw = (input_dir / f"{record}.txt").read_text(encoding="utf-8")
        direct = _load_direct(direct_dir / f"{record}.json")
        reviews = _load_reviews(critic_dir / f"{record}.json")
        response_audit.update(_response_audit(
            baseline[record],
            direct_dir / f"{record}.json",
            critic_dir / f"{record}.json",
        ))
        rows = [dict(row) for row in baseline[record]]
        for index, row in enumerate(rows):
            proposed = direct.get(index)
            review = reviews.get(index)
            if proposed is None or review is None:
                continue
            reviewed = tuple(dict.fromkeys(review.get("assertions") or []))
            if set(proposed) != set(reviewed):
                invalid["stage_disagreement"] += 1
                continue
            evidence = review.get("evidence") or []
            evidence_labels = {
                item.get("label") for item in evidence
                if item.get("label") in ASSERTIONS and isinstance(item.get("quote"), str)
                and item["quote"] and item["quote"] in raw
            }
            if not set(reviewed) <= evidence_labels:
                invalid["positive_evidence_failure"] += 1
                continue
            old = tuple(row.get("assertions") or [])
            removed = set(old) - set(reviewed)
            removal_rows = review.get("removals") or []
            supported_removals = {
                item.get("label") for item in removal_rows
                if item.get("label") in ASSERTIONS
                and item.get("category") in REMOVAL_CATEGORIES
            }
            if not removed <= supported_removals:
                invalid["removal_reason_failure"] += 1
                continue
            if set(old) == set(reviewed):
                continue
            row["assertions"] = list(reviewed)
            changes.append({"record": record, "entity_index": index,
                            "text": row["text"], "type": row["type"],
                            "before": list(old), "after": list(reviewed),
                            "evidence": evidence, "removals": removal_rows})
        final[record] = rows

    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    frozen_ok = True
    for record in range(1, 101):
        for old, new in zip(baseline[record], final[record]):
            frozen_ok &= all(old.get(field) == new.get(field)
                             for field in ("text", "type", "position", "candidates"))
        (output_dir / f"{record}.json").write_text(
            json.dumps(final[record], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    validation = validate_output_dir(input_dir, output_dir, position_mode="raw")
    missing_or_malformed = sum(
        response_audit[key] for key in (
            "direct_missing", "direct_malformed", "critic_missing", "critic_malformed"
        )
    )
    response_expected = (
        response_audit["direct_expected"] + response_audit["critic_expected"]
    )
    malformed_rate = missing_or_malformed / response_expected if response_expected else 0.0
    gates = {
        "baseline_hash_matches": True,
        "qwen_model_id_matches": True,
        "at_least_80_and_at_most_500_assertion_rows_changed": 80 <= len(changes) <= 500,
        "all_non_assertion_fields_are_identical": frozen_ok,
        "zero_assertions_on_ineligible_types": all(
            not row.get("assertions") for rows in final.values() for row in rows
            if row["type"] not in ELIGIBLE_TYPES
        ),
        "malformed_or_missing_rate_at_most_0.01": malformed_rate <= 0.01,
        "all_positive_evidence_quotes_round_trip": invalid["positive_evidence_failure"] == 0,
        "all_100_records_validate": validation["ok"],
    }
    report: dict[str, Any] = {
        "hypothesis": "H62_two_stage_assertion_hybrid",
        "changes": len(changes),
        "records_changed": len({row["record"] for row in changes}),
        "transition_counts": dict(Counter(
            f"{tuple(row['before'])}->{tuple(row['after'])}" for row in changes)),
        "invalid": dict(invalid),
        "response_audit": dict(response_audit),
        "missing_or_malformed": missing_or_malformed,
        "response_expected": response_expected,
        "malformed_rate": malformed_rate,
        "changed_rows": changes,
        "validation": validation,
        "gates": gates,
        "decision": "PASS" if all(gates.values()) else "FAIL",
    }
    if report["decision"] == "PASS":
        package_output(output_dir, zip_path)
        first = _sha256(zip_path)
        repeat = zip_path.with_name(zip_path.stem + "_repeat.zip")
        package_output(output_dir, repeat)
        second = _sha256(repeat)
        repeat.unlink()
        report.update(zip_sha256=first, repeat_zip_sha256=second,
                      byte_identical_repeat=first == second)
        if first != second:
            zip_path.unlink()
            report["decision"] = "FAIL"
    elif zip_path.exists():
        zip_path.unlink()
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("direct", "critic", "build"):
        child = sub.add_parser(name)
        child.add_argument("--input", type=Path, default=Path("turn2/input"))
        child.add_argument("--baseline", type=Path, default=Path("turn2/output_v10_multiview_consensus"))
        child.add_argument("--direct", type=Path, default=Path("experiments/H62_assertion_hybrid/cache/direct"))
        child.add_argument("--critic", type=Path, default=Path("experiments/H62_assertion_hybrid/cache/critic"))
    critic_parser = sub.choices["critic"]
    critic_parser.add_argument("--start-record", type=int, default=1)
    critic_parser.add_argument("--end-record", type=int, default=100)
    build_parser = sub.choices["build"]
    build_parser.add_argument("--baseline-zip", type=Path, default=Path("turn2/output_v10_multiview_consensus.zip"))
    build_parser.add_argument("--output", type=Path, default=Path("turn2/output_v18_assertion_hybrid"))
    build_parser.add_argument("--zip", type=Path, default=Path("turn2/output_v18_assertion_hybrid.zip"))
    build_parser.add_argument("--report", type=Path, default=Path("experiments/H62_assertion_hybrid/results/report.json"))
    args = parser.parse_args()
    if args.command == "direct":
        result = direct_pass(args.input, args.baseline, args.direct)
    elif args.command == "critic":
        result = critic_pass(
            args.input, args.baseline, args.direct, args.critic,
            args.start_record, args.end_record,
        )
    else:
        result = build(args.input, args.baseline, args.baseline_zip, args.direct,
                       args.critic, args.output, args.zip)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        result = {key: value for key, value in result.items() if key != "changed_rows"}
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
