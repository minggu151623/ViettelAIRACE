from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def _load(directory: Path) -> dict[str, list[dict[str, Any]]]:
    return {
        path.stem: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.json"), key=lambda p: int(p.stem))
    }


def build_audit(
    baseline_dir: str | Path,
    precision_dir: str | Path,
    recall_dir: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    baseline = _load(Path(baseline_dir))
    precision = _load(Path(precision_dir))
    recall = _load(Path(recall_dir))

    def keys(rows):
        return {(tuple(e["position"]), e["type"], e["text"]) for e in rows}

    counts: dict[str, dict[str, int]] = {}
    for name, records in (("baseline", baseline), ("precision", precision), ("recall", recall)):
        counter = Counter(e["type"] for rows in records.values() for e in rows)
        counts[name] = dict(counter)
    new_precision, new_recall, empty_candidates = [], [], []
    for record_id in sorted(recall, key=int):
        base_keys = keys(baseline.get(record_id, []))
        precision_keys = keys(precision.get(record_id, []))
        for entity in precision.get(record_id, []):
            key = (tuple(entity["position"]), entity["type"], entity["text"])
            if key not in base_keys:
                new_precision.append({"record": record_id, **entity})
            if entity["type"] in {"THUỐC", "CHẨN_ĐOÁN"} and not entity.get("candidates"):
                empty_candidates.append({"record": record_id, **entity})
        for entity in recall.get(record_id, []):
            key = (tuple(entity["position"]), entity["type"], entity["text"])
            if key not in precision_keys:
                new_recall.append({"record": record_id, **entity})
    report = {
        "counts": counts,
        "new_precision_entities": len(new_precision),
        "new_recall_entities": len(new_recall),
        "precision_empty_candidates": len(empty_candidates),
        "samples": {
            "new_precision": new_precision[:100],
            "new_recall": new_recall[:100],
            "empty_candidates": empty_candidates[:100],
        },
    }
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report
