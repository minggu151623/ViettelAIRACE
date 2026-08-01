from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

from .assertions import attach_assertions
from .schema import ENTITY_TYPES, Entity
from .validator import validate_entities


CRITIC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "changes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "action": {
                        "type": "string",
                        "enum": ["REMOVE", "RETYPE"],
                    },
                    "type": {"type": "string", "enum": sorted(ENTITY_TYPES)},
                },
                "required": ["index", "action", "type"],
            },
        }
    },
    "required": ["changes"],
}

SYSTEM_PROMPT = """Bạn là reviewer annotation NER hồ sơ bệnh án tiếng Việt.
Bạn nhận TEXT và danh sách span đã được ground chính xác bằng index.
Chỉ quyết định loại và sửa TYPE; không tạo span mới.

Giữ một span khi nó là:
- CHẨN_ĐOÁN: bệnh, hội chứng, rối loạn, chấn thương hoặc phát hiện bệnh lý.
- TRIỆU_CHỨNG: than phiền, triệu chứng hoặc dấu hiệu của bệnh nhân.
- THUỐC: dược chất/chế phẩm, gồm liều/đường/tần suất liền kề.
- TÊN_XÉT_NGHIỆM: tên xét nghiệm, đo lường hoặc chẩn đoán hình ảnh.
- KẾT_QUẢ_XÉT_NGHIỆM: giá trị/kết luận của xét nghiệm.
- THÔNG_TIN_BỆNH_NHÂN: tuổi hoặc giới tính rõ ràng.

Loại:
- tiêu đề/nhãn mục, từ chung như bệnh lý, chẩn đoán, xét nghiệm, thuốc;
- phẫu thuật, thủ thuật, can thiệp và hành động điều trị;
- yếu tố nguy cơ/lối sống/địa điểm/thời gian/bộ phận cơ thể;
- span lồng bên trong một span đầy đủ cùng occurrence;
- câu mô tả dài không phải một concept.

Quy tắc quan trọng:
- phát hiện bệnh lý từ khám/hình ảnh là CHẨN_ĐOÁN, không phải TRIỆU_CHỨNG;
- không gọi tên thủ thuật là xét nghiệm hoặc thuốc;
- thuốc thật vẫn giữ trong câu thủ thuật, nhưng span phải là tên chế phẩm;
- Mặc định mọi index đều được GIỮ NGUYÊN.
- Chỉ trả trong changes những ngoại lệ thật sự cần REMOVE hoặc RETYPE.
- Nếu không có ngoại lệ, trả {"changes":[]}.
/no_think"""


def _request(model: str, text: str, entities: list[Entity], timeout: int = 600) -> dict[str, Any]:
    rows = [
        {
            "index": index,
            "text": entity.text,
            "type": entity.type,
            "position": list(entity.position),
        }
        for index, entity in enumerate(entities)
    ]
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "format": CRITIC_SCHEMA,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "<<<TEXT>>>\n"
                    + text
                    + "\n<<<ENTITIES>>>\n"
                    + json.dumps(rows, ensure_ascii=False)
                ),
            },
        ],
        "options": {
            "temperature": 0,
            "seed": 42,
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
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                result = json.loads(response.read().decode("utf-8"))
            content = result.get("message", {}).get("content", "{}")
            return content if isinstance(content, dict) else json.loads(content)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(attempt + 1)
    raise RuntimeError(f"Qwen critic request failed: {last_error}")


def review_entities(
    text: str, entities: list[Entity], model: str = "qwen3:8b"
) -> tuple[list[Entity], Counter[str]]:
    payload = _request(model, text, entities)
    by_index: dict[int, dict[str, Any]] = {}
    for row in payload.get("changes", []):
        try:
            index = int(row["index"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= index < len(entities) and index not in by_index:
            by_index[index] = row
    stats: Counter[str] = Counter()
    result: list[Entity] = []
    for index, entity in enumerate(entities):
        row = by_index.get(index)
        # Omission means keep: the critic only emits exceptional changes.
        if row is None:
            result.append(entity)
            continue
        if row.get("action") == "REMOVE":
            stats[f"removed:{entity.type}"] += 1
            continue
        new_type = (
            str(row.get("type", entity.type))
            if row.get("action") == "RETYPE"
            else entity.type
        )
        if new_type in ENTITY_TYPES and new_type != entity.type:
            stats[f"retyped:{entity.type}->{new_type}"] += 1
            entity.type = new_type
            entity.candidates = [] if new_type in {"CHẨN_ĐOÁN", "THUỐC"} else None
        result.append(entity)
    attach_assertions(result, text)
    result.sort(key=lambda entity: entity.position)
    validate_entities(result, text)
    return result, stats


def review_directory(
    input_dir: str | Path,
    source_dir: str | Path,
    output_dir: str | Path,
    report_path: str | Path | None = None,
    model: str = "qwen3:8b",
    records: set[str] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    inputs, source, output = Path(input_dir), Path(source_dir), Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    paths = sorted(inputs.glob("*.txt"), key=lambda path: int(path.stem))
    if records:
        paths = [path for path in paths if path.stem in records]
    stats: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    for index, path in enumerate(paths, 1):
        try:
            text = path.read_text(encoding="utf-8")
            entities = [
                Entity.from_dict(value)
                for value in json.loads(
                    (source / f"{path.stem}.json").read_text(encoding="utf-8")
                )
            ]
            reviewed, row_stats = review_entities(text, entities, model)
            stats.update(row_stats)
            stats["output_entities"] += len(reviewed)
            (output / f"{path.stem}.json").write_text(
                json.dumps(
                    [entity.to_dict() for entity in reviewed],
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            print(
                f"[{index:03d}/{len(paths):03d}] {path.name}: "
                f"{len(entities)} -> {len(reviewed)}",
                flush=True,
            )
        except Exception as exc:
            errors.append({"record": path.stem, "error": str(exc)})
    report = {
        "records": len(paths),
        "completed": len(paths) - len(errors),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "model": model,
        "source": str(source),
        "output": str(output),
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
