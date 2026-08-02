"""Controlled dual-prompt review of H35 novel agreements."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from .independent_agreement import KNOWN_HAZARDS, key
from .normalize import normalize_key
from .phrase_verifier import BOUNDARY_PROMPT, SEMANTIC_PROMPT, _request
from .proposals import load_proposals


CONTROL_TYPES = ("CHẨN_ĐOÁN", "TRIỆU_CHỨNG", "THUỐC")


def select_positive_controls(predictions: str | Path, h23_dir: str | Path,
                             vietmed_dir: str | Path, per_type: int = 10) -> list[dict[str, Any]]:
    rows = json.loads(Path(predictions).read_text(encoding="utf-8"))
    h23 = set()
    vietmed = set()
    for record in range(1, 101):
        for item in json.loads((Path(h23_dir) / f"{record}.json").read_text(encoding="utf-8")):
            h23.add((item["position"][0], item["position"][1], item["type"], record))
        vietmed.update((item.position[0], item.position[1], item.type, record)
                       for item in load_proposals(Path(vietmed_dir) / f"{record}.json"))
    pool = [row for row in rows if key(row) in h23 and key(row) in vietmed
            and row["type"] in CONTROL_TYPES]
    selected = []
    for kind in CONTROL_TYPES:
        subset = [row for row in pool if row["type"] == kind]
        subset.sort(key=lambda row: hashlib.sha256(
            f"6007:{row['record']}:{row['position'][0]}:{row['position'][1]}:{kind}".encode()
        ).hexdigest())
        selected.extend(subset[:per_type])
    return selected


def _review_rows(rows: list[dict[str, Any]], output_path: str | Path,
                 batch_size: int = 18) -> dict[str, Any]:
    digest = hashlib.sha256(json.dumps(
        [{k: v for k, v in row.items() if k != "expected"} for row in rows],
        ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    target = Path(output_path)
    if target.exists():
        cached = json.loads(target.read_text(encoding="utf-8"))
        if cached.get("digest") == digest:
            return cached
    semantic, boundary = {}, {}
    request_rows = [{"id": row["id"], "text": row["text"], "type": row["type"],
                     "record_support": row.get("record_support", 1),
                     "context": row["context"]} for row in rows]
    for offset in range(0, len(rows), batch_size):
        batch = request_rows[offset:offset + batch_size]
        semantic.update(_request(batch, SEMANTIC_PROMPT, 3109))
        boundary.update(_request(batch, BOUNDARY_PROMPT, 7823))
        print(f"H36 review {min(offset + batch_size, len(rows))}/{len(rows)}", flush=True)
    reviewed = []
    for row in rows:
        left, right = semantic.get(row["id"]), boundary.get(row["id"])
        hazard = normalize_key(row["text"]) in KNOWN_HAZARDS
        accepted = (left is not None and right is not None and
                    left["action"] == right["action"] == "KEEP" and not hazard)
        reviewed.append({**row, "semantic": left, "boundary": right,
                         "hazard": hazard, "accepted": accepted})
    artifact = {"digest": digest, "rows": reviewed}
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return artifact


def run_experiment(h35_report: str | Path, predictions: str | Path,
                   input_dir: str | Path, h23_dir: str | Path,
                   vietmed_dir: str | Path, output_dir: str | Path) -> dict[str, Any]:
    novel = json.loads(Path(h35_report).read_text(encoding="utf-8"))["queue"]
    positives = select_positive_controls(predictions, h23_dir, vietmed_dir)
    rows = []
    for group, values in (("novel", novel), ("positive_control", positives)):
        for value in values:
            raw = (Path(input_dir) / f"{value['record']}.txt").read_text(encoding="utf-8")
            start, end = value["position"]
            rows.append({"id": len(rows), "group": group, "record": value["record"],
                         "position": [start, end], "text": value["text"],
                         "type": value["type"], "confidence": value["confidence"],
                         "expected": "KEEP" if group == "positive_control" else None,
                         "context": raw[max(0, start - 180):start] + "⟦" + raw[start:end] + "⟧" + raw[end:min(len(raw), end + 180)]})
    output = Path(output_dir)
    review = _review_rows(rows, output / "review.json")
    reviewed = review["rows"]
    controls = [row for row in reviewed if row["group"] == "positive_control"]
    negatives = [row for row in reviewed if row["hazard"]]
    novel_rows = [row for row in reviewed if row["group"] == "novel"]
    complete = all(row["semantic"] is not None and row["boundary"] is not None
                   for row in reviewed)
    agreement = sum(row["semantic"] is not None and row["boundary"] is not None and
                    row["semantic"]["action"] == row["boundary"]["action"]
                    for row in reviewed) / max(1, len(reviewed))
    positive_retention = sum(row["accepted"] for row in controls) / max(1, len(controls))
    negative_drop = sum(not row["accepted"] for row in negatives) / max(1, len(negatives))
    offsets_valid = all((Path(input_dir) / f"{row['record']}.txt").read_text(encoding="utf-8")[row["position"][0]:row["position"][1]] == row["text"]
                        for row in reviewed)
    gates = {"responses_complete": complete,
             "positive_control_retention_at_least_0_85": positive_retention >= 0.85,
             "negative_control_drop_rate_equals_1": negative_drop == 1.0,
             "prompt_action_agreement_at_least_0_80": agreement >= 0.80,
             "all_offsets_valid": offsets_valid}
    accepted = [row for row in novel_rows if row["accepted"]]
    (output / "accepted_novel.json").write_text(
        json.dumps(accepted, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {"novel_rows": len(novel_rows), "positive_controls": len(controls),
              "negative_controls": len(negatives), "positive_retention": positive_retention,
              "negative_drop_rate": negative_drop, "prompt_action_agreement": agreement,
              "accepted_novel": len(accepted), "gates": gates,
              "status": "passed" if all(gates.values()) else "failed"}
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--h35", default="experiments/H35_independent_agreement_audit/results/report.json")
    parser.add_argument("--predictions", default="experiments/H34_minimum_epoch_recovery/results/combined_oof_predictions.json")
    parser.add_argument("--input", default="turn2/input")
    parser.add_argument("--h23", default="turn2/output_v8_candidate_semantic")
    parser.add_argument("--vietmed", default="experiments/H_turn2_multimodel_core/proposals_vietmed")
    parser.add_argument("--output", default="experiments/H36_controlled_novel_verifier/results")
    args = parser.parse_args()
    print(json.dumps(run_experiment(args.h35, args.predictions, args.input,
                                    args.h23, args.vietmed, args.output),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
