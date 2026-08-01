from __future__ import annotations

import json
import re
import time
from collections import Counter
from pathlib import Path
from typing import Any

from .assertions import attach_assertions
from .schema import Entity
from .validator import validate_entities


GENERIC_EXACT = {
    "bệnh nội khoa",
    "bệnh lý nội khoa",
    "bệnh lý",
    "bệnh mãn tính",
    "bệnh mạn tính",
    "thuốc",
    "chẩn đoán",
    "xét nghiệm",
    "kết quả",
    "thủ thuật",
    "can thiệp",
}
ATTRIBUTE_PREFIX = re.compile(
    r"^(?:vị\s*trí|thời\s*điểm|yếu\s*tố|đặc\s*điểm)\s*:",
    re.IGNORECASE,
)
PROCEDURE_CUES = re.compile(
    r"\b(?:phẫu\s*thuật|thủ\s*thuật|bypass|đặt\s+stent|đặt\s+shunt|"
    r"dẫn\s+lưu|nạo\s+vét|cắt\s+bỏ|khâu|nội\s+soi|can\s+thiệp)\b",
    re.IGNORECASE,
)
FALSE_DRUG_CUES = re.compile(
    r"^(?:gây\s+dính\s+màng\s+phổi\s+bằng\s+)?talc$|"
    r"^(?:truyền\s+dịch|khí\s+dung|oxy|o2)$",
    re.IGNORECASE,
)
PATHOLOGY_CUES = re.compile(
    r"\b(?:ung\s*thư|u\b|viêm|nhiễm|hẹp|tắc|vỡ|tràn\s*dịch|"
    r"xuất\s*huyết|nhồi\s*máu|suy|rối\s*loạn|tổn\s*thương|"
    r"gãy|loét|xơ|thoái\s*hóa)\b",
    re.IGNORECASE,
)
COAGULATION_PRODUCT = re.compile(
    r"(?:yếu\s*tố|factor)\s+(?:vii|viii|ix|xi|7|8|9|11)"
    r"(?:\s+(?:đậm\s*đặc|cô\s*đặc|concentrate))?",
    re.IGNORECASE,
)
DRUG_ACTION_PREFIX = re.compile(r"^\s*(?:tăng|giảm)\s+liều\s+", re.IGNORECASE)
DRUG_INDICATION_SUFFIX = re.compile(
    r"\s+(?:để|nhằm)\s+(?:an\s+thần|điều\s+trị|giảm|kiểm\s+soát)\b",
    re.IGNORECASE,
)
DRUG_GLUE_SUFFIX = re.compile(
    r"(?<=[A-Za-z])đã\s+(?:dừng|ngừng|hết)\b",
    re.IGNORECASE,
)


def _line(text: str, entity: Entity) -> str:
    start = text.rfind("\n", 0, entity.position[0]) + 1
    end = text.find("\n", entity.position[1])
    if end < 0:
        end = len(text)
    return text[start:end]


def _is_procedure_context(text: str, entity: Entity) -> bool:
    line = _line(text, entity)
    prefix = line[: max(0, entity.position[0] - (text.rfind("\n", 0, entity.position[0]) + 1))]
    before = text[max(0, entity.position[0] - 100):entity.position[0]]
    if bool(
        re.search(
            r"(?:tiền\s*sử\s+phẫu\s*thuật|các?\s+thủ\s*thuật|"
            r"thủ\s*thuật\s+(?:đã\s+)?thực\s*hiện)[^\n]*$",
            before,
            re.IGNORECASE,
        )
        or re.search(
            r"(?:tiền\s*sử\s+phẫu\s*thuật|các?\s+thủ\s*thuật|"
            r"thủ\s*thuật\s+(?:đã\s+)?thực\s*hiện)\s*:",
            prefix,
            re.IGNORECASE,
        )
    ):
        return True
    # Bullet lines inherit the closest section heading. Limit the lookup to
    # the current major numbered section so a remote surgical history heading
    # cannot leak into the current illness.
    before_section = text[:entity.position[0]]
    major = list(re.finditer(r"(?:^|\n)\s*\d+\.\s*", before_section))
    if major:
        before_section = before_section[major[-1].start():]
    procedure_heading = list(
        re.finditer(
            r"(?:^|\n)\s*(?:tiền\s*sử\s+phẫu\s*thuật\s*/\s*thủ\s*thuật|"
            r"các?\s+thủ\s*thuật(?:\s+đã)?\s+thực\s+hiện|"
            r"thủ\s*thuật\s+thực\s+hiện)\s*:?",
            before_section,
            re.IGNORECASE,
        )
    )
    competing_heading = list(
        re.finditer(
            r"(?:^|\n)\s*(?:thuốc|các?\s+bệnh|bệnh\s+lý|triệu\s*chứng|"
            r"kết\s+quả|chẩn\s*đoán|diễn\s+biến)\b[^\n]*",
            before_section,
            re.IGNORECASE,
        )
    )
    last_procedure = procedure_heading[-1].start() if procedure_heading else -1
    last_competing = competing_heading[-1].start() if competing_heading else -1
    return last_procedure > last_competing


def _overlap(a: Entity, b: Entity) -> bool:
    return a.position[0] < b.position[1] and b.position[0] < a.position[1]


def _structural_cleanup(
    text: str, entities: list[Entity], stats: Counter[str]
) -> list[Entity]:
    kept: list[Entity] = []
    for entity in entities:
        coagulation = COAGULATION_PRODUCT.search(entity.text)
        if coagulation:
            start = entity.position[0] + coagulation.start()
            end = entity.position[0] + coagulation.end()
            entity.text = text[start:end]
            entity.position = (start, end)
            entity.type = "THUỐC"
            entity.candidates = []
            stats["retyped:coagulation_product_to_drug"] += 1
        key = re.sub(r"\s+", " ", entity.text.casefold()).strip(" .,:;-")
        if entity.type == "THUỐC":
            prefix = DRUG_ACTION_PREFIX.match(entity.text)
            if prefix:
                start = entity.position[0] + prefix.end()
                entity.position = (start, entity.position[1])
                entity.text = text[start:entity.position[1]]
                stats["trimmed:drug_action_prefix"] += 1
            suffix = DRUG_INDICATION_SUFFIX.search(entity.text)
            if suffix:
                end = entity.position[0] + suffix.start()
                entity.position = (entity.position[0], end)
                entity.text = text[entity.position[0]:end].rstrip()
                entity.position = (
                    entity.position[0],
                    entity.position[0] + len(entity.text),
                )
                stats["trimmed:drug_indication_suffix"] += 1
            glued = DRUG_GLUE_SUFFIX.search(entity.text)
            if glued:
                end = entity.position[0] + glued.start()
                entity.position = (entity.position[0], end)
                entity.text = text[entity.position[0]:end]
                stats["trimmed:drug_glued_history_suffix"] += 1
            key = re.sub(r"\s+", " ", entity.text.casefold()).strip(" .,:;-")
        # Remove short symptom fragments grounded inside a larger token. This
        # catches already-generated artifacts ("ho" in "thoáng"/"khoa", or
        # truncated "ngà" in "ngày") while preserving legitimate standalone
        # short symptoms such as "ho" and "sốt".
        if entity.type == "TRIỆU_CHỨNG" and len(key) <= 4:
            start, end = entity.position
            left = text[start - 1:start] if start else ""
            right = text[end:end + 1]
            if (left and (left.isalnum() or left == "_")) or (
                right and (right.isalnum() or right == "_")
            ):
                stats["removed:embedded_short_symptom"] += 1
                continue
        if key in GENERIC_EXACT:
            stats["removed:generic"] += 1
            continue
        if entity.type == "TRIỆU_CHỨNG" and ATTRIBUTE_PREFIX.match(entity.text):
            stats["removed:attribute_value"] += 1
            continue
        if entity.type == "THUỐC" and FALSE_DRUG_CUES.fullmatch(entity.text.strip()):
            stats["removed:false_drug"] += 1
            continue
        if (
            entity.type in {"CHẨN_ĐOÁN", "TÊN_XÉT_NGHIỆM"}
            and PROCEDURE_CUES.search(entity.text)
            and _is_procedure_context(text, entity)
        ):
            stats["removed:procedure"] += 1
            continue
        if entity.type == "TÊN_XÉT_NGHIỆM" and re.match(
            r"^\s*(?:điều\s*trị|xử\s*trí)\b", entity.text, re.IGNORECASE
        ):
            stats["removed:treatment_as_test"] += 1
            continue
        # Clinical examination and imaging "findings" are problems/diagnoses,
        # not patient-reported symptoms. Only change when the pathology cue is
        # explicit; wrong types are doubly penalized.
        if (
            entity.type == "TRIỆU_CHỨNG"
            and PATHOLOGY_CUES.search(entity.text)
            and re.search(
                r"(?:lâm\s*sàng|khám|kết\s+quả\s+chẩn\s+đoán\s+hình\s+ảnh)\s*:",
                _line(text, entity)[: max(0, entity.position[0] - (text.rfind("\n", 0, entity.position[0]) + 1))],
                re.IGNORECASE,
            )
        ):
            entity.type = "CHẨN_ĐOÁN"
            entity.candidates = []
            stats["retyped:finding_to_diagnosis"] += 1
        kept.append(entity)

    # Qwen occasionally emits an inner symptom and a full diagnosis for the
    # exact same occurrence. The organiser counts a wrong extra type twice.
    result: list[Entity] = []
    for entity in kept:
        if entity.type == "TRIỆU_CHỨNG" and any(
            other.type == "CHẨN_ĐOÁN"
            and other.position[0] <= entity.position[0]
            and entity.position[1] <= other.position[1]
            for other in kept
        ):
            stats["removed:nested_wrong_type"] += 1
            continue
        result.append(entity)
    return result


def rebuild_v6(
    input_dir: str | Path,
    source_dir: str | Path,
    output_dir: str | Path,
    report_path: str | Path | None = None,
    structural_cleanup: bool = False,
) -> dict[str, Any]:
    """Create the controlled RxNorm-only V6 ablation.

    The organiser's specification demonstrates RxNorm candidates for drugs but
    never names ICD-10 as the diagnosis candidate ontology. Therefore diagnosis
    candidates are reset to the empty set instead of submitting an unsupported
    code system. Drug candidates and all raw offsets remain unchanged.
    """
    started = time.perf_counter()
    inputs, source, output = Path(input_dir), Path(source_dir), Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stats: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    records = sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem))
    for path in records:
        try:
            text = path.read_text(encoding="utf-8")
            values = json.loads((source / f"{path.stem}.json").read_text(encoding="utf-8"))
            entities = [Entity.from_dict(value) for value in values]
            for entity in entities:
                if entity.type == "CHẨN_ĐOÁN" and entity.candidates:
                    stats["removed_diagnosis_candidate_entities"] += 1
                    stats["removed_diagnosis_candidate_ids"] += len(entity.candidates)
                    entity.candidates = []
            if structural_cleanup:
                entities = _structural_cleanup(text, entities, stats)
                attach_assertions(entities, text)
            entities.sort(key=lambda entity: entity.position)
            validate_entities(entities, text)
            stats.update(f"output:{entity.type}" for entity in entities)
            stats["output_entities"] += len(entities)
            stats["drug_candidate_entities"] += sum(
                entity.type == "THUỐC" and bool(entity.candidates) for entity in entities
            )
            (output / f"{path.stem}.json").write_text(
                json.dumps(
                    [entity.to_dict() for entity in entities],
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            errors.append({"record": path.stem, "error": str(exc)})
    report = {
        "records": len(records),
        "completed": len(records) - len(errors),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "source": str(source),
        "output": str(output),
        "candidate_policy": "RxNorm for THUỐC; empty candidates for CHẨN_ĐOÁN",
        "structural_cleanup": structural_cleanup,
        "stats": dict(stats),
        "errors": errors,
    }
    if report_path:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return report
