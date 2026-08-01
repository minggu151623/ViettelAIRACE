from __future__ import annotations

import json
import re
import time
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

from .normalize import normalize_key
from .schema import Entity, entities_from_json
from .validator import validate_entities


ICD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "mappings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "mention": {"type": "string"},
                    "code": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["mention", "code", "confidence"],
            },
        }
    },
    "required": ["mappings"],
}

ICD_SYSTEM_PROMPT = """Bạn là chuyên gia mã hóa ICD-10-CM.
Với từng mention chẩn đoán tiếng Việt, chọn đúng MỘT mã ICD-10-CM cụ thể nhất.
- Dùng mã ICD-10-CM, không dùng ICD-10 WHO rút gọn, SNOMED hay ICD-9.
- Nếu mention chỉ là tiêu đề, thủ thuật, triệu chứng chưa thành chẩn đoán, hoặc
  không đủ chắc chắn thì code là chuỗi rỗng.
- Giữ nguyên trường mention như đầu vào.
- confidence nằm trong [0,1].
- Không giải thích và không thêm mention mới.
/no_think"""


def _default_codes_path() -> Path:
    return (
        Path(__file__).resolve().parent
        / "resources"
        / "icd10cm_2026"
        / "icd10cm-codes-2026.txt"
    )


def load_icd10cm_codes(path: str | Path | None = None) -> dict[str, str]:
    source = Path(path) if path else _default_codes_path()
    codes: dict[str, str] = {}
    for line in source.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        code, _, title = line.partition(" ")
        codes[code.strip().upper()] = title.strip()
    return codes


def _compact_code(value: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", value.upper())


def _display_code(compact: str) -> str:
    return compact if len(compact) <= 3 else f"{compact[:3]}.{compact[3:]}"


def _request_icd_batch(
    mentions: list[str],
    model: str,
    seed: int,
    timeout: int = 600,
) -> list[dict[str, Any]]:
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "format": ICD_SCHEMA,
        "messages": [
            {"role": "system", "content": ICD_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps({"mentions": mentions}, ensure_ascii=False),
            },
        ],
        "options": {
            "temperature": 0,
            "seed": seed,
            "num_ctx": 16384,
            "num_predict": 2048,
        },
    }
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    content = body.get("message", {}).get("content", "{}")
    return list(json.loads(content).get("mappings", []))


def collect_unlinked_diagnoses(source_dir: str | Path) -> list[str]:
    source = Path(source_dir)
    mentions: dict[str, str] = {}
    for path in sorted(source.glob("*.json"), key=lambda value: int(value.stem)):
        for entity in json.loads(path.read_text(encoding="utf-8")):
            if entity.get("type") != "CHẨN_ĐOÁN" or entity.get("candidates"):
                continue
            text = str(entity.get("text", "")).strip()
            if text:
                mentions.setdefault(normalize_key(text), text)
    return [mentions[key] for key in sorted(mentions)]


def prepare_icd_aliases(
    source_dir: str | Path,
    output_path: str | Path,
    model: str = "qwen3:8b",
    batch_size: int = 32,
    min_confidence: float = 0.72,
) -> dict[str, Any]:
    """Build a reusable alias map using two independent deterministic passes."""

    started = time.perf_counter()
    mentions = collect_unlinked_diagnoses(source_dir)
    valid_codes = load_icd10cm_codes()
    accepted: dict[str, dict[str, Any]] = {}
    disagreements: list[dict[str, Any]] = []
    for offset in range(0, len(mentions), batch_size):
        batch = mentions[offset:offset + batch_size]
        first = {
            normalize_key(str(row.get("mention", ""))): row
            for row in _request_icd_batch(batch, model, seed=42)
        }
        second = {
            normalize_key(str(row.get("mention", ""))): row
            for row in _request_icd_batch(batch, model, seed=137)
        }
        for mention in batch:
            key = normalize_key(mention)
            left, right = first.get(key, {}), second.get(key, {})
            left_code = _compact_code(str(left.get("code", "")))
            right_code = _compact_code(str(right.get("code", "")))
            left_conf = float(left.get("confidence", 0) or 0)
            right_conf = float(right.get("confidence", 0) or 0)
            if (
                left_code
                and left_code == right_code
                and left_code in valid_codes
                and min(left_conf, right_conf) >= min_confidence
            ):
                accepted[key] = {
                    "mention": mention,
                    "code": _display_code(left_code),
                    "title": valid_codes[left_code],
                    "confidence": round(min(left_conf, right_conf), 4),
                    "agreement": 2,
                }
            else:
                disagreements.append(
                    {
                        "mention": mention,
                        "first": _display_code(left_code) if left_code else "",
                        "second": _display_code(right_code) if right_code else "",
                        "first_confidence": left_conf,
                        "second_confidence": right_conf,
                    }
                )
    artifact = {
        "ontology": "ICD-10-CM FY2026",
        "model": model,
        "method": "two-pass exact-code agreement",
        "min_confidence": min_confidence,
        "aliases": accepted,
        "rejected": disagreements,
    }
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(artifact, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "mentions": len(mentions),
        "accepted": len(accepted),
        "rejected": len(disagreements),
        "output": str(target),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


_DIAGNOSIS_NOISE = {
    "bệnh hiện tại",
    "bệnh nội khoa",
    "bệnh lý bất thường",
    "phân giai đoạn phẫu thuật",
}
_TEST_NOISE = {
    "bipap",
    "chuyển nhịp bằng sốc điện đồng bộ",
    "động mạch cảnh chung trái",
    "không chẩn đoán được",
    "mạch",
    "ntg",
    "ổn định",
}

# High-precision aliases whose clinical meaning and ICD-10-CM code are
# unambiguous. The LLM-generated map is retained for audit, but only this
# reviewed subset is allowed into a submission artifact.
_SAFE_ICD_OVERRIDES = {
    "bệnh gan do rượu": "K70.9",
    "bệnh gút không đặc hiệu": "M10.9",
    "béo phì": "E66.9",
    "bệnh trào ngược dạ dày- thực quản không có viêm thực quản": "K21.9",
    "herpes simplex (hsv)": "B00.9",
    "nhiễm khuẩn đường tiết niệu": "N39.0",
    "nhiễm trùng huyết": "A41.9",
    "nhiễm trùng đường hô hấp trên cấp": "J06.9",
    "rối loạn lipid máu": "E78.9",
    "rối loạn lo âu": "F41.1",
    "rối loạn lo âu, không biệt định nghiêm trọng": "F41.1",
    "rối loạn lưỡng cực": "F31.9",
    "tâm thần phân liệt": "F20.9",
    "tăng sản tuyến tiền liệt": "N40.1",
    "suy tim": "I50.9",
    "tăng kali máu": "E87.5",
    "tăng áp lực tĩnh mạch cửa": "K76.6",
    "hội chứng não gan": "K76.82",
    "viêm dạ dày ruột do virus": "A08.4",
    "viêm túi mật": "K81.9",
    "viêm phổi bệnh viện": "J18.9",
    "thuyên tắc mạch phổi": "I26.99",
    "bệnh động mạch vành": "I25.1",
    "khối u trực tràng": "C20",
    "tái phát u ác trực tràng": "C20",
}


def _is_strong_noise(entity: Entity) -> bool:
    key = normalize_key(entity.text)
    if entity.type == "CHẨN_ĐOÁN" and key in _DIAGNOSIS_NOISE:
        return True
    if entity.type == "TÊN_XÉT_NGHIỆM" and key in _TEST_NOISE:
        return True
    if entity.type == "THUỐC" and not entity.candidates:
        # These are orders/classes without a drug ingredient, not linkable
        # medication concepts under the official example convention.
        if key in {
            "40meq po k",
            "40meq iv k",
            "kháng sinh tĩnh mạch",
        }:
            return True
    if entity.type == "THÔNG_TIN_BỆNH_NHÂN":
        if len(entity.text.split()) > 6 or "cháu gái" in key:
            return True
    return False


def reconcile_v5(
    input_dir: str | Path,
    source_dir: str | Path,
    aliases_path: str | Path,
    output_dir: str | Path,
    report_path: str | Path | None = None,
    enable_icd: bool = True,
) -> dict[str, Any]:
    started = time.perf_counter()
    input_path, source_path = Path(input_dir), Path(source_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    artifact = json.loads(Path(aliases_path).read_text(encoding="utf-8"))
    aliases = artifact.get("aliases", {})
    valid_codes = load_icd10cm_codes()
    safe_overrides = {
        normalize_key(key): code for key, code in _SAFE_ICD_OVERRIDES.items()
    }
    counts: Counter[str] = Counter()
    added_codes: Counter[str] = Counter()
    removed_noise: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    records = sorted(input_path.glob("*.txt"), key=lambda path: int(path.stem))
    for text_path in records:
        try:
            text = text_path.read_text(encoding="utf-8")
            entities = entities_from_json(
                json.loads(
                    (source_path / f"{text_path.stem}.json").read_text(encoding="utf-8")
                )
            )
            kept: list[Entity] = []
            for entity in entities:
                if _is_strong_noise(entity):
                    removed_noise[entity.type] += 1
                    continue
                if entity.type == "CHẨN_ĐOÁN" and not entity.candidates:
                    # Only reviewed, high-precision aliases are activated.
                    # The complete two-pass LLM map remains in the report for
                    # later human review but is not trusted blindly.
                    compact = _compact_code(
                        safe_overrides.get(normalize_key(entity.text), "")
                    ) if enable_icd else ""
                    if compact in valid_codes:
                        entity.candidates = [_display_code(compact)]
                        added_codes[entity.candidates[0]] += 1
                kept.append(entity)
            validate_entities(kept, text)
            counts.update(entity.type for entity in kept)
            (output_path / f"{text_path.stem}.json").write_text(
                json.dumps(
                    [entity.to_dict() for entity in kept],
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            errors.append({"record": text_path.stem, "error": str(exc)})
            (output_path / f"{text_path.stem}.json").write_text("[]\n", encoding="utf-8")
    report = {
        "records": len(records),
        "entity_counts": dict(counts),
        "added_candidate_entities": sum(added_codes.values()),
        "added_candidate_codes": dict(added_codes),
        "removed_noise": dict(removed_noise),
        "errors": errors,
        "source": str(source_path),
        "aliases": str(aliases_path),
        "enable_icd": enable_icd,
        "output": str(output_path),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    if report_path:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return report
