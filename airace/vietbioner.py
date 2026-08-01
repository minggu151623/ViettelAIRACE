from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SOURCE_TYPE = "DiagnosticProcedure"
TARGET_TYPE = "TÊN_XÉT_NGHIỆM"


def _sentences(path: Path) -> list[list[tuple[str, str]]]:
    rows: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            if current:
                rows.append(current)
                current = []
            continue
        token, tag = line.rsplit(maxsplit=1)
        current.append((token, tag))
    if current:
        rows.append(current)
    return rows


def _convert_sentence(tokens: list[tuple[str, str]], record_id: str) -> dict[str, Any]:
    text_parts: list[str] = []
    token_offsets: list[tuple[int, int]] = []
    cursor = 0
    for index, (token, _) in enumerate(tokens):
        if index:
            text_parts.append(" ")
            cursor += 1
        text_parts.append(token)
        token_offsets.append((cursor, cursor + len(token)))
        cursor += len(token)
    text = "".join(text_parts)

    entities: list[dict[str, Any]] = []
    start: int | None = None
    end = 0
    for index, (_, tag) in enumerate(tokens + [("", "O")]):
        active = tag == f"I-{SOURCE_TYPE}"
        if active and start is None:
            start, end = token_offsets[index]
        elif active:
            end = token_offsets[index][1]
        elif start is not None:
            entities.append(
                {
                    "text": text[start:end],
                    "type": TARGET_TYPE,
                    "assertions": [],
                    "position": [start, end],
                }
            )
            start = None
    return {"record_id": record_id, "text": text, "entities": entities}


def prepare_vietbioner_transfer(source_dir: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Create a licensed, BTC-schema-safe transfer corpus from VietBioNER.

    Only DiagnosticProcedure is retained and mapped to TÊN_XÉT_NGHIỆM. The
    source's combined Symptom_and_Disease label is deliberately excluded.
    """
    source = Path(source_dir)
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    source_splits = {"train": "train", "valid": "dev", "test": "test"}
    report: dict[str, Any] = {
        "source": str(source),
        "mapping": {SOURCE_TYPE: TARGET_TYPE},
        "excluded_source_labels": ["Symptom_and_Disease", "Location", "DateTime", "Organisation"],
        "splits": {},
    }
    for output_name, source_name in source_splits.items():
        path = source / "data_supervised_learning" / f"{source_name}.txt"
        converted = [
            _convert_sentence(sentence, f"vietbioner-{output_name}-{index:04d}")
            for index, sentence in enumerate(_sentences(path), 1)
        ]
        output = target / f"{output_name}.jsonl"
        payload = "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in converted)
        output.write_text(payload, encoding="utf-8")
        report["splits"][output_name] = {
            "examples": len(converted),
            "diagnostic_procedure_entities": sum(len(row["entities"]) for row in converted),
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "output_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
        }
    (target / "manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report
