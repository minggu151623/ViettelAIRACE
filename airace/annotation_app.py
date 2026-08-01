from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import streamlit as st

from airace.schema import ASSERTIONS, CANDIDATE_TYPES, ENTITY_TYPES, Entity
from airace.validator import validate_entities


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="input")
    parser.add_argument("--pred", default="output")
    parser.add_argument("--out", default="labels/annotations.jsonl")
    parser.add_argument(
        "--records",
        default=None,
        help="Optional comma-separated record ids for a blinded calibration queue.",
    )
    return parser.parse_args(sys.argv[1:])


def _load_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _editor_rows(values: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "text": value.get("text", ""),
            "type": value.get("type", ""),
            "start": int((value.get("position") or [0, 0])[0]),
            "end": int((value.get("position") or [0, 0])[1]),
            "assertions": ", ".join(value.get("assertions") or []),
            "candidates": ", ".join(value.get("candidates") or []),
        }
        for value in values
    ]


def _parse_csv(value: Any) -> list[str]:
    return [
        item.strip()
        for item in str(value or "").split(",")
        if item.strip()
    ]


def _to_entities(table: Any, text: str) -> list[Entity]:
    records = table.to_dict("records") if hasattr(table, "to_dict") else list(table)
    entities: list[Entity] = []
    for index, row in enumerate(records, 1):
        mention = str(row.get("text") or "").strip()
        kind = str(row.get("type") or "").strip()
        if not mention and not kind:
            continue
        if kind not in ENTITY_TYPES:
            raise ValueError(f"Dòng {index}: type không hợp lệ: {kind!r}")
        start = int(row.get("start", -1))
        end = int(row.get("end", -1))
        if not (0 <= start < end <= len(text)) or text[start:end] != mention:
            # A reviewer may change the text before updating offsets. If the
            # mention occurs exactly once, ground it safely; otherwise require a
            # deliberate offset choice.
            positions = []
            cursor = 0
            while mention:
                found = text.find(mention, cursor)
                if found < 0:
                    break
                positions.append(found)
                cursor = found + 1
            if len(positions) == 1:
                start, end = positions[0], positions[0] + len(mention)
            else:
                raise ValueError(
                    f"Dòng {index}: offset không khớp text; mention xuất hiện "
                    f"{len(positions)} lần, hãy chọn start/end chính xác."
                )
        assertions = _parse_csv(row.get("assertions"))
        invalid_assertions = set(assertions) - ASSERTIONS
        if invalid_assertions:
            raise ValueError(
                f"Dòng {index}: assertion không hợp lệ: {sorted(invalid_assertions)}"
            )
        candidates = _parse_csv(row.get("candidates"))
        entities.append(
            Entity(
                text=mention,
                type=kind,
                position=(start, end),
                assertions=assertions,
                candidates=candidates if kind in CANDIDATE_TYPES else None,
                source="human",
                confidence=1.0,
            )
        )
    entities.sort(key=lambda entity: entity.position)
    validate_entities(entities, text)
    return entities


args = _args()
input_dir, pred_dir, out_path = Path(args.input), Path(args.pred), Path(args.out)
files = sorted(input_dir.glob("*.txt"), key=lambda path: int(path.stem))
if args.records:
    selected = {
        value.strip() for value in args.records.split(",") if value.strip()
    }
    files = [path for path in files if path.stem in selected]
if not files:
    st.error(f"Không tìm thấy file .txt trong {input_dir}")
    st.stop()

saved_rows = _load_rows(out_path)
saved_by_id = {str(row.get("record_id")): row for row in saved_rows}
st.set_page_config(page_title="AIRace span review", layout="wide")
st.title("AIRace — duyệt span/type")
st.caption(
    "Ưu tiên sửa đúng text, type và offset. Assertion/candidate chỉ sửa sau khi span đã đúng."
)
st.progress(len(saved_by_id) / len(files))
st.write(f"Đã duyệt **{len(saved_by_id)}/{len(files)}** hồ sơ")

record = st.selectbox(
    "Hồ sơ",
    files,
    format_func=lambda path: (
        f"{path.stem} ✓" if path.stem in saved_by_id else path.stem
    ),
)
text = record.read_text(encoding="utf-8")
prediction_path = pred_dir / f"{record.stem}.json"
if record.stem in saved_by_id:
    prediction = saved_by_id[record.stem].get("entities", [])
elif prediction_path.exists():
    prediction = json.loads(prediction_path.read_text(encoding="utf-8"))
else:
    prediction = []

left, right = st.columns([1.05, 1])
with left:
    st.subheader("Văn bản gốc")
    st.text_area(
        "raw_text",
        text,
        height=650,
        disabled=True,
        label_visibility="collapsed",
    )
with right:
    st.subheader("Thực thể")
    edited = st.data_editor(
        _editor_rows(prediction),
        num_rows="dynamic",
        height=650,
        use_container_width=True,
        column_config={
            "type": st.column_config.SelectboxColumn(
                "type", options=sorted(ENTITY_TYPES), required=True
            ),
            "start": st.column_config.NumberColumn("start", min_value=0, step=1),
            "end": st.column_config.NumberColumn("end", min_value=1, step=1),
            "assertions": st.column_config.TextColumn(
                "assertions", help="Phân tách bằng dấu phẩy"
            ),
            "candidates": st.column_config.TextColumn(
                "candidates", help="ICD/RxCUI, phân tách bằng dấu phẩy"
            ),
        },
        key=f"entities-{record.stem}",
    )

if st.button("Lưu hồ sơ đã duyệt", type="primary"):
    try:
        entities = _to_entities(edited, text)
        rows = [
            row for row in _load_rows(out_path)
            if str(row.get("record_id")) != record.stem
        ]
        rows.append(
            {
                "record_id": record.stem,
                "text": text,
                "entities": [entity.to_dict() for entity in entities],
                "reviewed": True,
            }
        )
        rows.sort(key=lambda row: int(row["record_id"]))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
            encoding="utf-8",
        )
        st.success(
            f"Đã lưu {len(entities)} thực thể của hồ sơ {record.stem} vào {out_path}"
        )
    except Exception as exc:
        st.error(str(exc))
