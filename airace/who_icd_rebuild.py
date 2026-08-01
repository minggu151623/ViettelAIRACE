from __future__ import annotations

import json
import re
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .normalize import normalize_key
from .schema import Entity, entities_from_json
from .validator import validate_entities


_CODE_RE = re.compile(r"^[A-Z][0-9]{2}(?:\.[0-9A-Z]+)?$")
_PROPOSE_SCHEMA = {
    "type": "object",
    "properties": {
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "codes": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number"},
                },
                "required": ["id", "codes", "confidence"],
            },
        }
    },
    "required": ["rows"],
}
_REVIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "keep_codes": {"type": "array", "items": {"type": "string"}},
                    "confidence": {"type": "number"},
                },
                "required": ["id", "keep_codes", "confidence"],
            },
        }
    },
    "required": ["rows"],
}
_PROPOSE_PROMPT = """Bạn là chuyên gia mã hóa WHO ICD-10, không dùng ICD-10-CM của Mỹ.
Với mỗi mention CHẨN_ĐOÁN và ngữ cảnh, đề xuất 0-2 mã WHO ICD-10 phù hợp nhất.
Có thể trả cả mã nhóm 3 ký tự và mã cụ thể khi cả hai đều là candidate hợp lý.
Không mã hóa triệu chứng chung, kết quả xét nghiệm, thủ thuật, giải phẫu, câu phủ
định không phải chẩn đoán, hoặc text nhiễu. Nếu không chắc, trả codes rỗng.
Không sao chép mù mã hiện tại vì chúng có thể thuộc ICD-10-CM. /no_think"""
_REVIEW_PROMPT = """Bạn là giám khảo WHO ICD-10. Mỗi row có mention, ngữ cảnh và
một pool mã đã được xác nhận tồn tại trong WHO ICD-10 2019 cùng tiêu đề chính
thức. Chỉ chọn `keep_codes` từ pool; không được tạo mã mới. Giữ tối đa hai mã.
Có thể giữ cả category 3 ký tự và child cụ thể nếu cả hai cùng mô tả đúng mention,
theo chính sách candidates nhiều lựa chọn. Loại mã sai bệnh, sai nguyên nhân,
sai cơ quan hoặc suy diễn quá mức. Nếu mention không thực sự là chẩn đoán, giữ
rỗng. Trả đủ mọi id theo JSON schema. /no_think"""

# H19 is intentionally a small, auditable policy layer rather than another
# generative pass.  These are exact surface forms whose WHO code is either
# explicit in the mention or whose old code was demonstrably from a different
# disease family.  Values are restricted to the frozen WHO 2019 catalogue.
_H19_EXACT: dict[str, list[str]] = {
    normalize_key("Bệnh amyloidosis chuỗi nhẹ"): ["E85"],
    normalize_key("Bệnh amyloidosis tự miễn dịch"): ["E85"],
    normalize_key("bệnh ba thân động mạch vành nghiêm trọng"): ["I25.1"],
    normalize_key("bệnh gout"): ["M10.9"],
    normalize_key("bệnh mạch vành"): ["I25.1"],
    normalize_key("Bệnh phổi kẽ"): ["J84.9"],
    normalize_key("Bệnh phổi kẽ do sử dụng corticoid liều cao kéo dài"): ["J84.9"],
    normalize_key("chẩn đoán viêm dạ dày ruột do virus"): ["A08.4"],
    normalize_key("chẩn đoán Viêm mô tế bào"): ["L03.9"],
    normalize_key("Cơn đau thắt ngực không ổn định-bệnh tăng HA vô căn(nguyên phát)"): ["I20.0", "I10"],
    normalize_key("dị tật bẩm sinh"): ["Q89.9"],
    normalize_key("hội chứng Parkinson"): ["G20"],
    normalize_key("Kawasaki"): ["M30.3"],
    normalize_key("nhiễm khuẩn huyết"): ["A41.9"],
    normalize_key("nhiễm khuẩn tiết niệu"): ["N39.0"],
    normalize_key("Rối loạn lipid máu"): ["E78.5"],
    normalize_key("Rung nhĩ kèm đáp ứng thất nhanh"): ["I48.9"],
    normalize_key("suy thận cấp"): ["N17.9"],
    normalize_key("Tăng áp lực động mạch phổi nhẹ"): ["I27.2"],
    normalize_key("Tăng HA độ III đáp ứng với thuốc"): ["I10"],
    normalize_key("thiếu men G6PD"): ["D55.0"],
    normalize_key("tình trạng thiếu men G6PD"): ["D55.0"],
    normalize_key("tụ máu dưới màng cứng mạn tính"): ["I62.0"],
    normalize_key("Ung thư biểu mô tế bào vảy xâm nhập của dương vậtbiệt hóa kém"): ["C60.9"],
    normalize_key("ung thư cổ tử cung"): ["C53.9"],
    normalize_key("viêm bể thận"): ["N12"],
    normalize_key("viêm cầu thận"): ["N05.9"],
    normalize_key("Viêm cầu thận mạn"): ["N03.9"],
    normalize_key("Viêm cơ tim"): ["I40.9"],
    normalize_key("Viêm hang vị sung huyết"): ["K29.7"],
    normalize_key("viêm khớp dạng thấp"): ["M06.9"],
    normalize_key("viêm nang lông"): ["L73.9"],
    normalize_key("viêm phế quản"): ["J40"],
    normalize_key("Viêm phổi"): ["J18.9"],
    normalize_key("Viêm phổi hoại tử"): ["J85.0"],
    normalize_key("Viêm phổi bệnh viện"): ["J18.9"],
    normalize_key("viêm xoang"): ["J32.9"],
    normalize_key("viêm xương tủy"): ["M86.9"],
    normalize_key("phù gai thị"): ["H47.1"],
    normalize_key("Đợt cấp COPD"): ["J44.1"],
    normalize_key("Tâm phế mạn"): ["I27.9"],
    normalize_key("Xơ vữa động mạch vành"): ["I25.1"],
    normalize_key("đại tràng giãn"): ["K59.3"],
    normalize_key("đột quỵ"): ["I64"],
    normalize_key("đột tử"): ["R96"],
    normalize_key("hội chứng nghiện rượu"): ["F10.2"],
    normalize_key("ổ loét trong bao tử"): ["K25.9"],
}

_H19_FORCE_EMPTY = {
    normalize_key(value)
    for value in (
        "chăm sóc da mụn",
        "hang vị",
        "hệ thần kinh",
        "hồi tràng",
        "họ Lyssaviridae",
        "nước bọt",
        "phẫu thuật cắt cụt chân trái trên gối và chân phải dưới gối",
        "stent mạch vành",
        "sung huyết đỏ",
        "tủy sống",
        "đại não",
        "điều trị",
    )
}


def load_who_icd10(path: str | Path | None = None) -> dict[str, str]:
    source = Path(path) if path else (
        Path(__file__).resolve().parent
        / "resources"
        / "icd10_2019"
        / "icd102019syst_codes.txt"
    )
    codes: dict[str, str] = {}
    for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
        fields = line.split(";")
        if len(fields) < 9:
            continue
        code = fields[6].strip().upper()
        if _CODE_RE.fullmatch(code):
            codes[code] = fields[8].strip()
    return codes


def _local_context(raw_text: str, start: int, end: int) -> str:
    left, right = max(0, start - 150), min(len(raw_text), end + 150)
    return raw_text[left:start] + "⟦" + raw_text[start:end] + "⟧" + raw_text[end:right]


def collect_unique_diagnoses(
    input_dir: str | Path, source_dir: str | Path
) -> list[dict[str, Any]]:
    inputs, source = Path(input_dir), Path(source_dir)
    grouped: dict[str, dict[str, Any]] = {}
    for path in sorted(source.glob("*.json"), key=lambda item: int(item.stem)):
        raw_text = (inputs / f"{path.stem}.txt").read_text(encoding="utf-8")
        for value in json.loads(path.read_text(encoding="utf-8")):
            if value["type"] != "CHẨN_ĐOÁN":
                continue
            key = normalize_key(value["text"])
            row = grouped.setdefault(
                key,
                {
                    "key": key,
                    "texts": Counter(),
                    "current_candidates": Counter(),
                    "contexts": [],
                    "uses": 0,
                },
            )
            row["texts"][value["text"]] += 1
            row["current_candidates"][tuple(value.get("candidates", []))] += 1
            row["uses"] += 1
            if len(row["contexts"]) < 2:
                start, end = value["position"]
                row["contexts"].append(_local_context(raw_text, start, end))
    rows: list[dict[str, Any]] = []
    for identifier, key in enumerate(sorted(grouped)):
        value = grouped[key]
        rows.append(
            {
                "id": identifier,
                "key": key,
                "text": value["texts"].most_common(1)[0][0],
                "uses": value["uses"],
                "current_candidate_sets": [
                    {"codes": list(codes), "uses": count}
                    for codes, count in value["current_candidates"].most_common()
                ],
                "contexts": value["contexts"],
            }
        )
    return rows


def _chat(model: str, schema: dict[str, Any], system: str, rows: list[dict[str, Any]], seed: int) -> dict[int, dict[str, Any]]:
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "format": schema,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps({"rows": rows}, ensure_ascii=False)},
        ],
        "options": {"temperature": 0, "seed": seed, "num_ctx": 32768, "num_predict": 4096},
    }
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=900) as response:
        body = json.loads(response.read().decode("utf-8"))
    content = body.get("message", {}).get("content", "{}")
    parsed = content if isinstance(content, dict) else json.loads(content)
    return {int(row["id"]): row for row in parsed.get("rows", [])}


def build_who_icd_review(
    input_dir: str | Path,
    source_dir: str | Path,
    output_path: str | Path,
    *,
    model: str = "qwen3:8b",
    batch_size: int = 32,
) -> dict[str, Any]:
    catalog = load_who_icd10()
    rows = collect_unique_diagnoses(input_dir, source_dir)
    proposals: dict[int, dict[str, Any]] = {}
    for offset in range(0, len(rows), batch_size):
        batch = [
            {
                "id": row["id"],
                "mention": row["text"],
                "contexts": row["contexts"],
                "current_candidates": row["current_candidate_sets"],
            }
            for row in rows[offset : offset + batch_size]
        ]
        proposals.update(_chat(model, _PROPOSE_SCHEMA, _PROPOSE_PROMPT, batch, 4401))

    review_inputs: list[dict[str, Any]] = []
    for row in rows:
        proposed = proposals.get(row["id"], {"codes": [], "confidence": 0.0})
        proposal_confidence = float(proposed.get("confidence", 0.0) or 0.0)
        pool: dict[str, set[str]] = defaultdict(set)
        for candidate_set in row["current_candidate_sets"]:
            for raw_code in candidate_set["codes"]:
                code = str(raw_code).upper()
                if code in catalog:
                    pool[code].add("current_exact")
                    if "." in code and code[:3] in catalog:
                        pool[code[:3]].add("parent_of_current")
                elif code[:3] in catalog:
                    pool[code[:3]].add("cm_to_who_parent")
        if proposal_confidence >= 0.90:
            for raw_code in proposed.get("codes", [])[:2]:
                code = str(raw_code).strip().upper()
                if code in catalog:
                    pool[code].add("qwen_proposal")
                    if "." in code and code[:3] in catalog:
                        pool[code[:3]].add("parent_of_proposal")
        row["proposal"] = {
            "codes": [str(code).upper() for code in proposed.get("codes", [])[:2]],
            "confidence": proposal_confidence,
        }
        row["pool"] = [
            {"code": code, "title": catalog[code], "origins": sorted(origins)}
            for code, origins in sorted(pool.items(), key=lambda item: (len(item[0]), item[0]))
        ]
        review_inputs.append(
            {
                "id": row["id"],
                "mention": row["text"],
                "contexts": row["contexts"],
                "candidate_pool": row["pool"],
            }
        )

    reviews: dict[int, dict[str, Any]] = {}
    for offset in range(0, len(review_inputs), batch_size):
        reviews.update(
            _chat(model, _REVIEW_SCHEMA, _REVIEW_PROMPT, review_inputs[offset : offset + batch_size], 8803)
        )

    changed_unique = 0
    for row in rows:
        review = reviews.get(row["id"], {"keep_codes": [], "confidence": 0.0})
        confidence = float(review.get("confidence", 0.0) or 0.0)
        requested = {str(code).upper() for code in review.get("keep_codes", [])}
        allowed: list[str] = []
        for item in row["pool"]:
            code, origins = item["code"], set(item["origins"])
            if "current_exact" in origins:
                allowed.append(code)
            elif code in requested and (
                confidence >= 0.90
                or ("cm_to_who_parent" in origins and confidence >= 0.85)
            ):
                allowed.append(code)
        # At most one category and one specific code; prefer reviewer order for
        # equally specific choices while keeping deterministic catalog order.
        categories = sorted(code for code in set(allowed) if "." not in code)
        specifics = sorted(code for code in set(allowed) if "." in code)
        final = (categories[:1] + specifics[:1])[:2]
        row["review"] = {
            "requested_keep_codes": sorted(requested),
            "confidence": confidence,
        }
        row["final_codes"] = final
        old_sets = {tuple(item["codes"]) for item in row["current_candidate_sets"]}
        row["changes_any_current_set"] = any(tuple(final) != old for old in old_sets)
        changed_unique += int(row["changes_any_current_set"])

    result = {
        "model": model,
        "catalog_codes": len(catalog),
        "unique_diagnoses": len(rows),
        "changed_unique": changed_unique,
        "rows": rows,
    }
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {key: value for key, value in result.items() if key != "rows"}


def merge_who_icd_review(
    input_dir: str | Path,
    source_dir: str | Path,
    review_path: str | Path,
    output_dir: str | Path,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    inputs, source, output = Path(input_dir), Path(source_dir), Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    review = json.loads(Path(review_path).read_text(encoding="utf-8"))
    mapping = {row["key"]: list(row["final_codes"]) for row in review["rows"]}
    changes: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for path in sorted(source.glob("*.json"), key=lambda item: int(item.stem)):
        raw_text = (inputs / f"{path.stem}.txt").read_text(encoding="utf-8")
        entities = entities_from_json(json.loads(path.read_text(encoding="utf-8")))
        for index, entity in enumerate(entities):
            if entity.type != "CHẨN_ĐOÁN":
                continue
            before = list(entity.candidates or [])
            after = mapping.get(normalize_key(entity.text), before)
            entity.candidates = after
            if before != after:
                changes.append(
                    {"record": path.stem, "entity_index": index, "text": entity.text, "before": before, "after": after}
                )
                counts["repaired_from_nonempty" if before else "filled_empty"] += 1
        validate_entities(entities, raw_text)
        (output / path.name).write_text(
            json.dumps([entity.to_dict() for entity in entities], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    report = {
        "source": str(source),
        "review": str(review_path),
        "records": 100,
        "candidate_changes": len(changes),
        "change_kinds": dict(counts),
        "changes": changes,
    }
    if report_path:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def build_h19_selection(
    review_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    """Create a family-consistent, reviewer-authoritative WHO candidate map.

    H18 exposed two implementation errors: old candidates survived even when
    the reviewer rejected them, and the alphabetical selector could combine a
    category from one disease family with a child from another.  H19 fixes
    those errors without another model call and records every decision.
    """

    catalog = load_who_icd10()
    review = json.loads(Path(review_path).read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    counts: Counter[str] = Counter()
    for source_row in review["rows"]:
        row = dict(source_row)
        key = row["key"]
        old = sorted(
            {
                str(code).upper()
                for item in row["current_candidate_sets"]
                for code in item["codes"]
            }
        )
        reason = "reviewer"
        if key in _H19_FORCE_EMPTY:
            final: list[str] = []
            reason = "non_diagnosis_surface"
        elif key in _H19_EXACT:
            final = list(_H19_EXACT[key])
            reason = "exact_who_correction"
        else:
            confidence = float(row.get("review", {}).get("confidence", 0.0) or 0.0)
            requested = [
                str(code).upper()
                for code in row.get("review", {}).get("requested_keep_codes", [])
                if str(code).upper() in catalog
            ]
            # Confidence outside [0, 1] is malformed and cannot authorize a
            # change. Reviewer decisions, unlike proposer confidences, were
            # well-calibrated in the frozen run.
            if not 0.90 <= confidence <= 1.0:
                final = []
                reason = "reviewer_abstained"
            else:
                final = list(dict.fromkeys(requested))
                # A parent+child pair is allowed only inside one WHO family.
                # Two categories are retained only for an explicitly compound
                # surface such as "thủy đậu/Zona".
                families = defaultdict(list)
                for code in final:
                    families[code[:3]].append(code)
                if len(families) > 1 and not re.search(r"(?:/|\bvà\b|\bhoặc\b)", row["text"], re.I):
                    proposal_families = [
                        str(code).upper()[:3]
                        for code in row.get("proposal", {}).get("codes", [])
                        if str(code).upper() in catalog
                    ]
                    chosen = next((family for family in proposal_families if family in families), sorted(families)[0])
                    final = families[chosen]
                    reason = "reviewer_family_reconciled"
                # Prefer a specific code, with its category only when the
                # reviewer explicitly selected both. Never keep two children.
                if len(final) > 2:
                    specifics = [code for code in final if "." in code]
                    category = next((code for code in final if "." not in code), None)
                    final = ([category] if category and specifics and category[:3] == specifics[0][:3] else []) + specifics[:1]
                final = final[:2]
        invalid = [code for code in final if code not in catalog]
        if invalid:
            raise ValueError(f"H19 exact map contains non-WHO codes: {invalid}")
        row["h19_codes"] = final
        row["h19_reason"] = reason
        row["h19_changed"] = old != sorted(final)
        counts[reason] += row["uses"]
        if row["h19_changed"]:
            counts["changed_entity_uses"] += row["uses"]
            counts["changed_unique"] += 1
        rows.append(row)

    result = {
        "source_review": str(review_path),
        "catalog_codes": len(catalog),
        "unique_diagnoses": len(rows),
        "counts": dict(sorted(counts.items())),
        "rows": rows,
    }
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {key: value for key, value in result.items() if key != "rows"}


def merge_h19_selection(
    input_dir: str | Path,
    source_dir: str | Path,
    selection_path: str | Path,
    output_dir: str | Path,
    report_path: str | Path | None = None,
) -> dict[str, Any]:
    selection = json.loads(Path(selection_path).read_text(encoding="utf-8"))
    adapted = dict(selection)
    adapted["rows"] = [
        {**row, "final_codes": row["h19_codes"]} for row in selection["rows"]
    ]
    temporary = Path(selection_path).with_suffix(".merge.json")
    temporary.write_text(json.dumps(adapted, ensure_ascii=False), encoding="utf-8")
    try:
        return merge_who_icd_review(input_dir, source_dir, temporary, output_dir, report_path)
    finally:
        temporary.unlink(missing_ok=True)
