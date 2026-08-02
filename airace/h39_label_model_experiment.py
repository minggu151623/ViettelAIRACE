"""Run the preregistered early gates for H39 without creating an artifact."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from .dependency_label_model import ABSTAIN, DependencyAwareLabelModel, synthetic_correlated_noise
from .multiview_consensus import (EXPECTED_VIEW_SHA256, H34_PATH, VIEW_DIRS,
                                  _load_views, frozen_digest)


LABELS = ("DROP", "CHẨN_ĐOÁN", "TRIỆU_CHỨNG", "TÊN_XÉT_NGHIỆM",
          "KẾT_QUẢ_XÉT_NGHIỆM", "THUỐC", "THÔNG_TIN_BỆNH_NHÂN")
LABEL_INDEX = {label: index for index, label in enumerate(LABELS)}
SOURCE_NAMES = ("bami_v15", "bami_v3", "vietmed", "qwen_guarded", "h34_oof")
EXPECTED_H38_SHA256 = "a9b9ae07997e57080ed8ce2ad9c390f4cd8c229e8eae8de447f6f47ae6ff4d0b"
FAMILIES = {
    "bami": (0, 1),
    "vietmed": (2,),
    "qwen_guarded": (3,),
    "h34_oof": (4,),
}


def verify_hashes(input_dir: Path, baseline_zip: Path) -> dict[str, str]:
    observed = {name: frozen_digest(path) for name, path in VIEW_DIRS.items()}
    observed["h34_oof"] = frozen_digest(H34_PATH)
    observed["baseline_zip"] = hashlib.sha256(baseline_zip.read_bytes()).hexdigest()
    observed["input_tree"] = frozen_digest(input_dir)
    expected = {**EXPECTED_VIEW_SHA256,
                "baseline_zip": EXPECTED_H38_SHA256,
                "input_tree": "d68702073a5e478df60ab389b71587813ffac08475902f043446346ef0f15bcf"}
    mismatch = {key: {"expected": expected[key], "observed": value}
                for key, value in observed.items() if expected[key] != value}
    if mismatch:
        raise ValueError(f"H39 frozen source mismatch: {json.dumps(mismatch, sort_keys=True)}")
    return observed


def build_vote_matrix() -> tuple[list[tuple[int, int, int, str]], np.ndarray]:
    views, _ = _load_views()
    keys = sorted(set().union(*views.values()))
    by_source_record: list[dict[int, list[tuple[int, int, str]]]] = []
    for name in SOURCE_NAMES:
        records: dict[int, list[tuple[int, int, str]]] = defaultdict(list)
        for record, start, end, kind in views[name]:
            records[record].append((start, end, kind))
        by_source_record.append(records)

    votes = np.full((len(keys), len(SOURCE_NAMES)), ABSTAIN, dtype=np.int64)
    for row_index, (record, start, end, kind) in enumerate(keys):
        for source, records in enumerate(by_source_record):
            candidates = records.get(record, [])
            exact_position = [other_kind for left, right, other_kind in candidates
                              if left == start and right == end]
            if exact_position:
                chosen = kind if kind in exact_position else sorted(exact_position)[0]
                votes[row_index, source] = LABEL_INDEX[chosen]
            elif any(max(start, left) < min(end, right) for left, right, _ in candidates):
                votes[row_index, source] = LABEL_INDEX["DROP"]
    return keys, votes


def build_anchors(keys: list[tuple[int, int, int, str]], review_path: Path) -> tuple[np.ndarray, dict[str, int]]:
    anchors = np.full(len(keys), ABSTAIN, dtype=np.int64)
    index = {key: position for position, key in enumerate(keys)}
    counts: Counter[str] = Counter()
    review = json.loads(review_path.read_text(encoding="utf-8"))["rows"]
    for row in review:
        key = (int(row["record"]), int(row["position"][0]), int(row["position"][1]), str(row["type"]))
        if key not in index:
            continue
        if row["group"] == "positive_control":
            anchors[index[key]] = LABEL_INDEX[row["type"]]
            counts["positive"] += 1
        elif row["group"] == "negative_control":
            anchors[index[key]] = LABEL_INDEX["DROP"]
            counts["registered_hazard"] += 1
    for position, (_, start, end, kind) in enumerate(keys):
        if kind == "TRIỆU_CHỨNG" and anchors[position] == ABSTAIN:
            # The exact H38 anomaly class: a span beginning with a number and
            # containing no letters is a measurement, not a symptom mention.
            text = row_text(keys[position], start, end)
            if text and text[0].isdigit() and not any(char.isalpha() for char in text.replace("°C", "")):
                anchors[position] = LABEL_INDEX["DROP"]
                counts["numeric_measurement"] += 1
    return anchors, dict(counts)


def row_text(key: tuple[int, int, int, str], start: int, end: int,
             input_dir: Path = Path("turn2/input")) -> str:
    return (input_dir / f"{key[0]}.txt").read_text(encoding="utf-8")[start:end]


def combine_family_votes(votes: np.ndarray, columns: tuple[int, ...]) -> np.ndarray:
    selected = votes[:, columns]
    if len(columns) == 1:
        return selected[:, 0]
    combined = np.full(len(votes), ABSTAIN, dtype=np.int64)
    for row, values in enumerate(selected):
        active = values[values != ABSTAIN]
        if len(active) and np.all(active == active[0]):
            combined[row] = active[0]
    return combined


def majority_probabilities(votes: np.ndarray, family_columns: list[tuple[int, ...]]) -> np.ndarray:
    family_votes = np.column_stack([combine_family_votes(votes, columns) for columns in family_columns])
    probabilities = np.ones((len(votes), len(LABELS)), dtype=float)
    for label in range(len(LABELS)):
        probabilities[:, label] += np.sum(family_votes == label, axis=1)
    probabilities /= probabilities.sum(axis=1, keepdims=True)
    return probabilities


def leave_one_family_out(keys: list[tuple[int, int, int, str]], votes: np.ndarray,
                         anchors: np.ndarray) -> dict[str, Any]:
    reports = []
    all_pass = True
    for held_name, held_columns in FAMILIES.items():
        remaining_families = [columns for name, columns in FAMILIES.items() if name != held_name]
        remaining_columns = tuple(column for columns in remaining_families for column in columns)
        train_votes = votes[:, remaining_columns]
        weights = [0.5 if column in FAMILIES["bami"] else 1.0 for column in remaining_columns]
        model = DependencyAwareLabelModel(len(LABELS), weights, seed=3901)
        result = model.fit(train_votes, anchors)
        held_vote = combine_family_votes(votes, held_columns)
        majority = majority_probabilities(votes, remaining_families)
        for label, kind in enumerate(LABELS[1:], start=1):
            active = held_vote == label
            if active.sum() < 20:
                continue
            model_loss = float(-np.mean(np.log(np.clip(result.posterior[active, label], 1e-12, 1.0))))
            majority_loss = float(-np.mean(np.log(np.clip(majority[active, label], 1e-12, 1.0))))
            passed = model_loss < majority_loss
            all_pass &= passed
            reports.append({"heldout_family": held_name, "type": kind,
                            "observations": int(active.sum()),
                            "label_model_logloss": model_loss,
                            "majority_logloss": majority_loss,
                            "gain": majority_loss - model_loss, "passed": passed})
    return {"cells": reports, "evaluated_cells": len(reports), "all_cells_passed": all_pass}


def run(input_dir: Path, baseline_zip: Path, review_path: Path) -> dict[str, Any]:
    hashes = verify_hashes(input_dir, baseline_zip)
    synthetic = synthetic_correlated_noise()
    keys, votes = build_vote_matrix()
    anchors, anchor_counts = build_anchors(keys, review_path)
    holdout = leave_one_family_out(keys, votes, anchors) if synthetic["gate_gain_at_least_0_05"] else None
    passed = bool(synthetic["gate_gain_at_least_0_05"] and holdout and holdout["all_cells_passed"])
    return {"status": "early_gates_passed" if passed else "failed_before_stacker",
            "frozen_hashes": hashes, "synthetic": synthetic,
            "real_candidate_rows": len(keys),
            "vote_coverage": {SOURCE_NAMES[index]: int(np.sum(votes[:, index] != ABSTAIN))
                              for index in range(len(SOURCE_NAMES))},
            "anchor_counts": anchor_counts, "leave_one_family_out": holdout,
            "gates": {"frozen_hashes_match": True,
                      "synthetic_gain_at_least_0_05": bool(synthetic["gate_gain_at_least_0_05"]),
                      "leave_one_family_out_all_cells_gain": bool(holdout and holdout["all_cells_passed"])}}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("turn2/input"))
    parser.add_argument("--baseline-zip", type=Path, default=Path("turn2/output_v10_multiview_consensus.zip"))
    parser.add_argument("--review", type=Path, default=Path("experiments/H38_multiview_consensus/results/review.json"))
    parser.add_argument("--output", type=Path, default=Path("experiments/H39_dependency_aware_label_model/results/early_gates.json"))
    args = parser.parse_args()
    report = run(args.input, args.baseline_zip, args.review)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
