from __future__ import annotations

import json
import re
import time
import urllib.request
import urllib.error
from collections import Counter
from pathlib import Path
from typing import Any

from .assertions import attach_assertions
from .candidates import CandidateResolver
from .detector import detect_entities
from .normalize import normalize_with_map
from .resources import load_lexicon
from .schema import ASSERTIONS, ENTITY_TYPES, Entity
from .validator import validate_entities


SYSTEM_PROMPT = """Bạn là hệ thống NER y khoa tiếng Việt.
Hãy trích xuất TẤT CẢ các khái niệm y khoa trong hồ sơ, không tóm tắt.

Nhãn hợp lệ:
- CHẨN_ĐOÁN: bệnh, rối loạn, hội chứng hoặc chẩn đoán đã xác định.
- TRIỆU_CHỨNG: triệu chứng, dấu hiệu, than phiền, kể cả bị phủ định.
- TÊN_XÉT_NGHIỆM: tên xét nghiệm, phép đo, chẩn đoán hình ảnh hoặc thủ thuật chẩn đoán.
- KẾT_QUẢ_XÉT_NGHIỆM: giá trị/kết quả cụ thể của xét nghiệm.
- THUỐC: tên thuốc; span phải gồm liều, dạng, đường dùng và tần suất liền kề nếu có.
- THÔNG_TIN_BỆNH_NHÂN: tuổi, giới, mã bệnh nhân hoặc thông tin định danh.

Quy tắc bắt buộc:
1. text phải là chuỗi con NGUYÊN VĂN, liên tục, xuất hiện trong INPUT.
2. Không tự tính offset. Mỗi cặp (text, type) chỉ xuất ĐÚNG MỘT LẦN dù
   chuỗi đó lặp lại nhiều lần trong INPUT; hệ thống sẽ tự tìm mọi occurrence.
3. Không xuất tiêu đề, nhãn mục, thời gian đơn thuần, hành động chăm sóc hoặc thủ thuật điều trị.
4. Không biến triệu chứng thành chẩn đoán.
5. assertions chỉ gồm:
   - isHistorical: bệnh/thuốc/triệu chứng thuộc tiền sử hoặc trước đợt hiện tại.
   - isNegated: khái niệm bị phủ định rõ ràng.
   - isFamily: khái niệm thuộc người thân, không phải bệnh nhân.
6. Với CHẨN_ĐOÁN, icd10 chỉ điền khi chắc chắn mã ICD-10; nếu không chắc để chuỗi rỗng.
7. Không lặp lại cùng một text/type trong JSON.
8. Chỉ trả JSON theo schema, không giải thích.
9. THUỐC chỉ là dược chất/chế phẩm. Tuyệt đối không gán thủ thuật, can thiệp,
   phẫu thuật, truyền dịch chung chung hoặc hành động điều trị thành THUỐC.
10. Span phải GỌN:
   - THUỐC dừng trước các cụm "điều trị", "cho", "do", "nhằm".
   - TÊN_XÉT_NGHIỆM chỉ chứa tên phép đo/chẩn đoán, không chứa hành động,
     thời điểm hay giá trị.
   - KẾT_QUẢ_XÉT_NGHIỆM chỉ chứa giá trị hoặc kết luận, không chứa tên xét nghiệm.
   Ví dụ "canxi 12.0" phải tách thành "canxi" và "12.0".
11. Không xuất hai span chồng lấn mô tả cùng một khái niệm. Với chuỗi triệu
    chứng độc lập như "lo âu mất ngủ", xuất "lo âu" và "mất ngủ" riêng.

Ví dụ 1:
INPUT = "Thuốc trước nhập viện: amlodipine 10 mg po daily; guaifenesin ml po q6h:prn điều trị ho"
OUTPUT = {"entities":[
  {"text":"amlodipine 10 mg po daily","type":"THUỐC","assertions":["isHistorical"],"icd10":""},
  {"text":"guaifenesin ml po q6h:prn","type":"THUỐC","assertions":["isHistorical"],"icd10":""},
  {"text":"ho","type":"TRIỆU_CHỨNG","assertions":[],"icd10":""}
]}

Ví dụ 2:
INPUT = "Tiền sử tăng huyết áp. Hiện không đau ngực. Troponin 0.10."
OUTPUT = {"entities":[
  {"text":"tăng huyết áp","type":"CHẨN_ĐOÁN","assertions":["isHistorical"],"icd10":"I10"},
  {"text":"đau ngực","type":"TRIỆU_CHỨNG","assertions":["isNegated"],"icd10":""},
  {"text":"Troponin","type":"TÊN_XÉT_NGHIỆM","assertions":[],"icd10":""},
  {"text":"0.10","type":"KẾT_QUẢ_XÉT_NGHIỆM","assertions":[],"icd10":""}
]}
/no_think"""

STRUCTURED_SYSTEM_PROMPT = """Bạn là annotator NER cho hồ sơ bệnh án tiếng Việt
được viết theo mẫu nhiều mục. Hãy trích xuất concept theo quy ước i2b2:
problem (CHẨN_ĐOÁN/TRIỆU_CHỨNG), test (TÊN_XÉT_NGHIỆM/KẾT_QUẢ_XÉT_NGHIỆM)
và treatment (THUỐC).

Ưu tiên span nguyên văn, đầy đủ và liên tục:
- Dòng bullet trong "các bệnh lý mãn tính" là một chẩn đoán hoàn chỉnh.
- Dòng bullet trong "triệu chứng hiện tại" là một triệu chứng hoàn chỉnh.
- Lý do nhập viện: tách các concept theo dấu phẩy/liên từ.
- Phát hiện bệnh lý sau khám/hình ảnh là CHẨN_ĐOÁN.
- THUỐC gồm tên + liều + dạng + đường + tần suất liền kề, dừng trước
  "điều trị", "cho", "do", "nhằm".
- Tên thủ thuật/phẫu thuật/dẫn lưu/bypass/đặt stent không phải thuốc và
  không phải xét nghiệm; nếu câu có thuốc thật thì chỉ lấy tên thuốc.
- Không lấy tiêu đề, nhãn section, thời gian, vị trí cơ thể đơn độc, yếu tố
  nguy cơ/lối sống hay câu mô tả chung.
- Mỗi occurrence ở vị trí khác nhau là entity riêng. Không gộp các occurrence.
- Không tạo ICD candidate nếu không chắc; output icd10 rỗng.
text bắt buộc là substring nguyên văn của INPUT; chỉ trả JSON schema."""


ENTITY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "entities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "type": {"type": "string", "enum": sorted(ENTITY_TYPES)},
                    "assertions": {
                        "type": "array",
                        "items": {"type": "string", "enum": sorted(ASSERTIONS)},
                    },
                    "icd10": {"type": "string"},
                },
                "required": ["text", "type", "assertions", "icd10"],
            },
        }
    },
    "required": ["entities"],
}


def _request_ollama(
    model: str,
    text: str,
    timeout: int = 600,
    prompt_profile: str = "broad",
) -> dict[str, Any]:
    system_prompt = (
        STRUCTURED_SYSTEM_PROMPT
        if prompt_profile == "structured"
        else SYSTEM_PROMPT
    )
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "format": ENTITY_SCHEMA,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "INPUT bắt đầu sau dòng này. Trả về entities theo thứ tự xuất hiện.\n"
                    "<<<INPUT>>>\n"
                    f"{text}\n"
                    "<<<END_INPUT>>>"
                ),
            },
        ],
        "options": {
            "temperature": 0,
            "seed": 42,
            "num_ctx": 16384,
            "num_predict": 1536,
        },
    }
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/chat",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last_error: Exception | None = None
    result: dict[str, Any] | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
            break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt == 2:
                raise
            time.sleep(1 + attempt)
    if result is None:
        raise RuntimeError(f"Ollama request failed: {last_error}")
    content = result.get("message", {}).get("content", "")
    if isinstance(content, dict):
        return content
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

    # A long structured answer can hit num_predict midway through the final
    # object. Recover every complete entity object preceding the cut instead of
    # discarding the whole record.
    array_start = content.find("[", content.find('"entities"'))
    if array_start >= 0:
        decoder = json.JSONDecoder()
        cursor = array_start + 1
        recovered: list[dict[str, Any]] = []
        while cursor < len(content):
            while cursor < len(content) and content[cursor] in " \t\r\n,":
                cursor += 1
            if cursor >= len(content) or content[cursor] == "]":
                break
            try:
                value, cursor = decoder.raw_decode(content, cursor)
            except json.JSONDecodeError:
                break
            if isinstance(value, dict):
                recovered.append(value)
        if recovered:
            return {"entities": recovered}
    raise ValueError(f"Ollama did not return recoverable JSON: {content[:200]!r}")


def _ground_span(raw: str, mention: str, proposed_start: int, used: set[tuple[int, int, str]]) -> tuple[int, int] | None:
    if mention and 0 <= proposed_start <= len(raw) - len(mention):
        end = proposed_start + len(mention)
        if raw[proposed_start:end] == mention:
            return proposed_start, end

    starts = [m.start() for m in re.finditer(re.escape(mention), raw, re.IGNORECASE)] if mention else []
    for start in starts:
        key = (start, start + len(mention), mention.casefold())
        if key not in used:
            return start, start + len(mention)

    # Last resort: tolerate whitespace differences while still returning an
    # exact raw substring and exact offsets.
    if mention.isascii() and len(mention) <= 3:
        return None
    normalized = normalize_with_map(raw)
    wanted = re.sub(r"\s+", " ", normalize_with_map(mention).value).strip()
    if not wanted:
        return None
    pattern = re.compile(r"\s+".join(re.escape(part) for part in wanted.split()))
    for match in pattern.finditer(normalized.value):
        start, end = normalized.raw_span(match.start(), match.end())
        key = (start, end, raw[start:end].casefold())
        if key not in used:
            return start, end
    return None


def extract_llm_entities(
    text: str,
    model: str = "qwen3:8b",
    prompt_profile: str = "broad",
) -> tuple[list[Entity], dict[str, int]]:
    payload = _request_ollama(model, text, prompt_profile=prompt_profile)
    entities: list[Entity] = []
    used: set[tuple[int, int, str]] = set()
    unique_mentions: set[tuple[str, str]] = set()
    rejected = Counter()
    for item in payload.get("entities", []):
        mention = str(item.get("text", "")).strip()
        kind = str(item.get("type", ""))
        if kind not in ENTITY_TYPES or not mention:
            rejected["invalid_schema"] += 1
            continue
        mention_key = (mention.casefold(), kind)
        if mention_key in unique_mentions:
            rejected["duplicate_concept"] += 1
            continue
        unique_mentions.add(mention_key)
        positions: list[tuple[int, int]] = []
        while True:
            position = _ground_span(text, mention, -1, used)
            if position is None:
                break
            positions.append(position)
            exact = text[position[0]:position[1]]
            used.add((position[0], position[1], exact.casefold()))
        if not positions:
            rejected["ungrounded"] += 1
            continue
        assertions = [value for value in item.get("assertions", []) if value in ASSERTIONS]
        candidates: list[str] | None = [] if kind in {"CHẨN_ĐOÁN", "THUỐC"} else None
        icd10 = str(item.get("icd10", "")).strip().upper()
        if kind == "CHẨN_ĐOÁN" and re.fullmatch(r"[A-Z]\d{2}(?:\.[A-Z0-9]{1,4})?", icd10):
            candidates = [icd10]
        for position in positions:
            entities.append(
                Entity(
                    text=text[position[0]:position[1]],
                    type=kind,
                    assertions=list(dict.fromkeys(assertions)),
                    position=position,
                    candidates=list(candidates) if candidates is not None else None,
                    confidence=0.86,
                    source="qwen3",
                )
            )
    entities.sort(key=lambda entity: entity.position)
    return entities, dict(rejected)


def _merge_high_precision_rules(text: str, entities: list[Entity]) -> list[Entity]:
    rule_entities = detect_entities(text, load_lexicon(), profile="baseline")
    attach_assertions(rule_entities, text)
    merged = list(entities)
    for rule in rule_entities:
        if rule.type not in {"THUỐC", "TÊN_XÉT_NGHIỆM", "KẾT_QUẢ_XÉT_NGHIỆM"}:
            continue
        overlaps = [
            entity
            for entity in merged
            if entity.type == rule.type
            and entity.position[0] < rule.position[1]
            and rule.position[0] < entity.position[1]
        ]
        if not overlaps:
            merged.append(rule)
    return sorted(merged, key=lambda entity: entity.position)


_RESULT_CUE = re.compile(
    r"\b(?:bình\s+thường|bất\s+thường|âm\s+tính|dương\s+tính|"
    r"không\s+(?:có|ghi\s+nhận|cho\s+thấy)|cao|thấp|tăng|giảm|"
    r"chiếm\s+ưu\s+thế|ngoại\s+tâm\s+thu|nhồi\s+máu|tổn\s+thương|"
    r"đám\s+mờ|đáng\s+chú\s+ý)\b",
    re.IGNORECASE,
)
_DRUG_EVIDENCE = re.compile(
    r"(?:\d+(?:[.,]\d+)?\s*(?:mg|mcg|g|ml|%|đơn\s*vị)\b|"
    r"\b(?:po|iv|im|sc|bid|tid|qid|q\d+h|prn|uống|tiêm|tĩnh\s+mạch|"
    r"dưới\s+lưỡi|khí\s+dung|nebs?)\b)",
    re.IGNORECASE,
)
_DRUG_STOP = re.compile(r"\s+(?:điều\s+trị|dùng\s+để|nhằm|cho|do)\s+", re.IGNORECASE)
_DRUG_TAIL = re.compile(r"(?:\s*:\s*prn|\s+prn)\b", re.IGNORECASE)


def _split_symptom(entity: Entity, text: str) -> list[Entity]:
    if entity.type != "TRIỆU_CHỨNG":
        return [entity]
    lexicon = load_lexicon()
    phrases = sorted(
        (str(value) for value, kind in lexicon.get("symptoms", {}).items() if kind == "TRIỆU_CHỨNG"),
        key=len,
        reverse=True,
    )
    found: list[tuple[int, int]] = []
    for phrase in phrases:
        for match in re.finditer(re.escape(phrase), entity.text, re.IGNORECASE):
            start, end = match.span()
            # A lexicon item must be a complete token/phrase, not an arbitrary
            # substring.  Without this guard the short symptom "ho" was split
            # out of Vietnamese words such as "thoáng", "khoa", "khoảng",
            # "hoặc", and "cho", creating dozens of false entities.
            left = entity.text[start - 1:start] if start else ""
            right = entity.text[end:end + 1]
            if (left and (left.isalnum() or left == "_")) or (
                right and (right.isalnum() or right == "_")
            ):
                continue
            if any(start < e and s < end for s, e in found):
                continue
            found.append((start, end))
    if len(found) <= 1:
        return [entity]
    result: list[Entity] = []
    for start, end in sorted(found):
        raw_start = entity.position[0] + start
        result.append(
            Entity(
                text=text[raw_start:entity.position[0] + end],
                type=entity.type,
                assertions=list(entity.assertions),
                position=(raw_start, entity.position[0] + end),
                candidates=None,
                confidence=entity.confidence,
                source=entity.source,
            )
        )
    return result


def _sanitize_entities(text: str, entities: list[Entity]) -> list[Entity]:
    """Remove systematic generative errors without inventing new spans."""
    cleaned: list[Entity] = []
    for entity in entities:
        if entity.type in {
            "TÊN_XÉT_NGHIỆM",
            "KẾT_QUẢ_XÉT_NGHIỆM",
            "THÔNG_TIN_BỆNH_NHÂN",
        }:
            entity.assertions = []
        if entity.type == "THUỐC":
            stop = _DRUG_STOP.search(entity.text)
            if stop:
                end = entity.position[0] + stop.start()
                entity.text = text[entity.position[0]:end].rstrip()
                entity.position = (entity.position[0], entity.position[0] + len(entity.text))
            if "(" in entity.text:
                end = entity.text.find("(")
                if end > 2:
                    entity.text = entity.text[:end].rstrip()
                    entity.position = (entity.position[0], entity.position[0] + len(entity.text))
            # Preserve a schedule suffix the model sometimes omits.
            tail = _DRUG_TAIL.match(text, entity.position[1])
            if tail:
                entity.position = (entity.position[0], tail.end())
                entity.text = text[entity.position[0]:entity.position[1]]
            if re.search(
                r"\b(?:đặt\s+đường\s+truyền|truyền\s+dịch|xông\s+khí\s+dung|"
                r"giai\s+đoạn\s+\d+\s+của\s+phẫu\s+thuật|phẫu\s+thuật\s+sửa)\b",
                entity.text,
                re.IGNORECASE,
            ):
                continue
            # A bare unknown phrase such as "thủ thuật can thiệp" is not a drug.
            if not entity.candidates and not _DRUG_EVIDENCE.search(entity.text):
                continue
        elif entity.type == "KẾT_QUẢ_XÉT_NGHIỆM":
            if (
                entity.text.strip().isdigit()
                and entity.position[1] < len(text)
                and text[entity.position[1]:entity.position[1] + 1] == "."
                and (entity.position[0] == 0 or text[entity.position[0] - 1] == "\n")
            ):
                continue
            # Models occasionally emit the analyte ("canxi") as the result.
            # Preserve the exact span but correct its type when no result signal exists.
            if not re.search(r"\d", entity.text) and not _RESULT_CUE.search(entity.text):
                if len(entity.text.split()) <= 5:
                    entity.type = "TÊN_XÉT_NGHIỆM"
                else:
                    continue
        elif entity.type == "TÊN_XÉT_NGHIỆM":
            # Reject sentence-sized descriptions that swallow several names/results.
            if len(entity.text.split()) > 12 or (
                len(entity.text.split()) > 7 and re.search(r"\d", entity.text)
            ):
                continue
            if re.search(
                r"\b(?:đặt\s+shunt|dẫn\s+lưu|phẫu\s+thuật|can\s+thiệp|"
                r"đặt\s+ống|cắt\s+bỏ|khâu)\b",
                entity.text,
                re.IGNORECASE,
            ):
                continue
            if re.fullmatch(r"(?:bình\s*thường\s*)+", entity.text, re.IGNORECASE):
                entity.type = "KẾT_QUẢ_XÉT_NGHIỆM"
        elif entity.type == "THÔNG_TIN_BỆNH_NHÂN":
            if not re.search(
                r"(?:\b(?:nam|nữ|tuổi|họ\s+tên|tên|địa\s+chỉ|số\s+điện\s+thoại|"
                r"sđt|mã\s+bệnh\s+nhân|mrn)\b|\d+\s*tuổi)",
                entity.text,
                re.IGNORECASE,
            ):
                continue
        elif entity.type == "TRIỆU_CHỨNG" and re.search(
            r"\b(?:mất\s+việc\s+làm|cà\s+phê|caffeine|rượu\s+bia|"
            r"thuốc\s+lá|thủ\s+thuật|can\s+thiệp)\b",
            entity.text,
            re.IGNORECASE,
        ):
            continue
        if not entity.text:
            continue
        cleaned.extend(_split_symptom(entity, text))

    # Prefer compact spans when a noisy same-type span contains a cleaner one.
    kept: list[Entity] = []
    for entity in sorted(cleaned, key=lambda item: (item.position[0], item.position[1])):
        duplicate = False
        for other in kept:
            if entity.type != other.type:
                continue
            if entity.position == other.position:
                duplicate = True
                break
            if entity.type in {"THUỐC", "TÊN_XÉT_NGHIỆM", "TRIỆU_CHỨNG", "CHẨN_ĐOÁN"}:
                a0, a1 = entity.position
                b0, b1 = other.position
                if a0 <= b0 and b1 <= a1 or b0 <= a0 and a1 <= b1:
                    prefer_short = entity.type in {"THUỐC", "TÊN_XÉT_NGHIỆM"}
                    entity_better = (
                        (a1 - a0) < (b1 - b0)
                        if prefer_short
                        else (a1 - a0) > (b1 - b0)
                    )
                    if entity_better:
                        kept.remove(other)
                        break
                    duplicate = True
                    break
        if not duplicate:
            kept.append(entity)
    return sorted(kept, key=lambda item: item.position)


def infer_llm_text(
    text: str,
    model: str = "qwen3:8b",
    resolver: CandidateResolver | None = None,
    merge_rules: bool = True,
    prompt_profile: str = "broad",
) -> tuple[list[Entity], dict[str, int]]:
    entities, rejected = extract_llm_entities(text, model, prompt_profile)
    attach_assertions(entities, text)
    if merge_rules:
        entities = _merge_high_precision_rules(text, entities)
    resolver = resolver or CandidateResolver()
    for entity in entities:
        if entity.type == "CHẨN_ĐOÁN" and entity.candidates:
            continue
        resolver.resolve(entity, text)
    entities = _sanitize_entities(text, entities)
    entities.sort(key=lambda entity: entity.position)
    validate_entities(entities, text)
    return entities, rejected


def infer_llm_directory(
    input_dir: str | Path,
    output_dir: str | Path,
    report_path: str | Path | None = None,
    model: str = "qwen3:8b",
    merge_rules: bool = True,
    resume: bool = True,
    prompt_profile: str = "broad",
    record_ids: set[str] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    inputs, outputs = Path(input_dir), Path(output_dir)
    outputs.mkdir(parents=True, exist_ok=True)
    resolver = CandidateResolver()
    counts: Counter[str] = Counter()
    rejected: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    records = sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem))
    if record_ids is not None:
        records = [path for path in records if path.stem in record_ids]
    for index, path in enumerate(records, 1):
        target = outputs / f"{path.stem}.json"
        try:
            if resume and target.exists():
                values = json.loads(target.read_text(encoding="utf-8"))
                entities = [Entity.from_dict(value) for value in values]
                text = path.read_text(encoding="utf-8")
                for entity in entities:
                    resolver.resolve(entity, text)
                entities = _sanitize_entities(text, entities)
                target.write_text(
                    json.dumps([entity.to_dict() for entity in entities], ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            else:
                text = path.read_text(encoding="utf-8")
                entities, rejected_row = infer_llm_text(
                    text,
                    model,
                    resolver,
                    merge_rules,
                    prompt_profile,
                )
                rejected.update(rejected_row)
                target.write_text(
                    json.dumps([entity.to_dict() for entity in entities], ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
            counts.update(entity.type for entity in entities)
            print(f"[{index:03d}/{len(records):03d}] {path.name}: {len(entities)} entities", flush=True)
        except Exception as exc:
            errors.append({"record": path.stem, "error": str(exc)})
            print(f"[{index:03d}/{len(records):03d}] {path.name}: ERROR {exc}", flush=True)
    report = {
        "records": len(records),
        "completed": len(records) - len(errors),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "entity_counts": dict(counts),
        "rejected": dict(rejected),
        "errors": errors,
        "offline": True,
        "model": model,
        "merge_rules": merge_rules,
        "prompt_profile": prompt_profile,
    }
    if report_path:
        target = Path(report_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
