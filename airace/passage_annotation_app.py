"""Streamlit UI for prediction-blind H41 passage annotation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import streamlit as st

from airace.passage_annotation import (
    context_for_occurrence,
    load_labels,
    save_label,
    validate_occurrence_assertions,
    validate_passage_entities,
)
from airace.schema import ENTITY_TYPES


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="turn2/input")
    parser.add_argument(
        "--manifest",
        default="experiments/H41_repeated_passage_blind_annotation/queue.json",
    )
    parser.add_argument("--out", required=True)
    parser.add_argument("--reviewer", required=True)
    return parser.parse_args(sys.argv[1:])


def _csv(value: Any) -> list[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


args = _args()
input_dir, manifest_path, out_path = Path(args.input), Path(args.manifest), Path(args.out)
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
labels = load_labels(out_path)
passages = manifest["passages"]

st.set_page_config(page_title="AIRace blind passage annotation", layout="wide")
st.title("AIRace H41 — gán nhãn đoạn lặp mù")
st.warning(
    "Không mở output/model trong lúc gán nhãn. Màn hình này chỉ hiển thị văn bản gốc. "
    "Nếu không chắc candidate ICD/RxCUI, hãy để trống."
)
st.progress(sum(row.get("stage_b_reviewed", False) for row in labels.values()) / len(passages))
st.write(
    f"Reviewer **{args.reviewer}** — hoàn tất "
    f"**{sum(row.get('stage_b_reviewed', False) for row in labels.values())}/{len(passages)}** đoạn"
)

chosen = st.selectbox(
    "Đoạn",
    passages,
    format_func=lambda row: (
        f"{row['passage_id'][:10]} · {row['stratum']} · "
        f"{row['distinct_record_count']} hồ sơ"
        + (" ✓" if labels.get(row["passage_id"], {}).get("stage_b_reviewed") else "")
    ),
)
passage_id, text = chosen["passage_id"], chosen["text"]
saved = labels.get(passage_id, {})

left, right = st.columns([1.05, 1])
with left:
    st.subheader("Văn bản nguyên gốc")
    st.text_area("passage", text, height=420, disabled=True, label_visibility="collapsed")
    st.caption(f"Độ dài {len(text)} ký tự · {len(chosen['occurrences'])} occurrence")
with right:
    st.subheader("A — span, type, candidate")
    initial = [
        {
            "text": row["text"],
            "type": row["type"],
            "start": row["position"][0],
            "end": row["position"][1],
            "candidates": ", ".join(row.get("candidates", [])),
        }
        for row in saved.get("entities", [])
    ]
    edited = st.data_editor(
        initial,
        num_rows="dynamic",
        height=420,
        use_container_width=True,
        column_config={
            "type": st.column_config.SelectboxColumn(
                "type", options=sorted(ENTITY_TYPES), required=True
            ),
            "start": st.column_config.NumberColumn("start", min_value=0, step=1),
            "end": st.column_config.NumberColumn("end", min_value=1, step=1),
            "candidates": st.column_config.TextColumn("candidates", help="Phân tách bằng dấu phẩy"),
        },
        key=f"stage-a-{passage_id}",
    )

if st.button("Lưu giai đoạn A", type="primary"):
    try:
        records = edited.to_dict("records") if hasattr(edited, "to_dict") else list(edited)
        entities = validate_passage_entities(
            text,
            [
                {
                    "text": str(row.get("text") or ""),
                    "type": str(row.get("type") or ""),
                    "position": [int(row.get("start", -1)), int(row.get("end", -1))],
                    "candidates": _csv(row.get("candidates")),
                }
                for row in records
                if str(row.get("text") or "").strip() or str(row.get("type") or "").strip()
            ],
        )
        row = {
            "passage_id": passage_id,
            "passage_sha256": passage_id,
            "reviewer_id": args.reviewer,
            "entities": entities,
            "occurrence_assertions": [],
            "stage_a_reviewed": True,
            "stage_b_reviewed": len(entities) == 0,
        }
        save_label(out_path, row)
        st.success("Đã lưu giai đoạn A. Tải lại trang để duyệt assertion.")
    except Exception as exc:
        st.error(str(exc))

entities = saved.get("entities", [])
if saved.get("stage_a_reviewed") and entities:
    st.divider()
    st.subheader("B — assertion riêng cho từng occurrence")
    occurrence = st.selectbox(
        "Occurrence",
        chosen["occurrences"],
        format_func=lambda row: f"Hồ sơ {row['record_id']} · offset {row['position']}",
    )
    st.text_area(
        "Ngữ cảnh ±200 ký tự",
        context_for_occurrence(input_dir, occurrence),
        height=250,
        disabled=True,
    )
    old = {
        item["entity_index"]: ", ".join(item.get("assertions", []))
        for item in saved.get("occurrence_assertions", [])
        if item["record_id"] == occurrence["record_id"]
        and item["occurrence_position"] == occurrence["position"]
    }
    assertion_rows = [
        {
            "entity_index": index,
            "text": entity["text"],
            "type": entity["type"],
            "assertions": old.get(index, ""),
        }
        for index, entity in enumerate(entities)
    ]
    assertion_edit = st.data_editor(
        assertion_rows,
        hide_index=True,
        disabled=["entity_index", "text", "type"],
        use_container_width=True,
        key=f"stage-b-{passage_id}-{occurrence['record_id']}-{occurrence['position'][0]}",
    )
    if st.button("Lưu assertion của occurrence"):
        current = [
            item
            for item in saved.get("occurrence_assertions", [])
            if not (
                item["record_id"] == occurrence["record_id"]
                and item["occurrence_position"] == occurrence["position"]
            )
        ]
        table = assertion_edit.to_dict("records") if hasattr(assertion_edit, "to_dict") else list(assertion_edit)
        current.extend(
            {
                "record_id": occurrence["record_id"],
                "occurrence_position": occurrence["position"],
                "entity_index": int(item["entity_index"]),
                "assertions": _csv(item.get("assertions")),
            }
            for item in table
        )
        try:
            current = validate_occurrence_assertions(entities, current)
            expected = len(entities) * len(chosen["occurrences"])
            saved["occurrence_assertions"] = current
            saved["stage_b_reviewed"] = len(current) == expected
            save_label(out_path, saved)
            st.success(
                f"Đã lưu. Assertion coverage {len(current)}/{expected}."
            )
        except Exception as exc:
            st.error(str(exc))
