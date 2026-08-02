from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def entity_key(record_id: str, entity: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record_id,
        entity["text"],
        entity["type"],
        int(entity["position"][0]),
        int(entity["position"][1]),
    )


def load_entities(directory: str | Path) -> dict[tuple[Any, ...], dict[str, Any]]:
    root = Path(directory)
    paths = sorted(root.glob("*.json"), key=lambda path: int(path.stem))
    if len(paths) != 100:
        raise ValueError(f"expected 100 records in {root}, found {len(paths)}")
    values: dict[tuple[Any, ...], dict[str, Any]] = {}
    for path in paths:
        for entity in json.loads(path.read_text(encoding="utf-8")):
            key = entity_key(path.stem, entity)
            if key in values:
                raise ValueError(f"duplicate exact entity key: {key}")
            values[key] = entity
    return values


def cohort_report(
    source: dict[tuple[Any, ...], dict[str, Any]],
    target: dict[tuple[Any, ...], dict[str, Any]],
    *,
    assertion_delta: float,
) -> dict[str, Any]:
    novel_keys = sorted(target.keys() - source.keys())
    removed_keys = sorted(source.keys() - target.keys())
    asserted = [(key, target[key]) for key in novel_keys if target[key].get("assertions")]
    labels = Counter(
        label for _, entity in asserted for label in entity.get("assertions", [])
    )
    records = sorted({key[0] for key, _ in asserted}, key=int)
    weighted_loss = 0.3 * abs(assertion_delta)
    return {
        "source_entities": len(source),
        "target_entities": len(target),
        "novel_entities": len(novel_keys),
        "removed_entities": len(removed_keys),
        "asserted_novel_entities": len(asserted),
        "asserted_fraction": len(asserted) / len(novel_keys) if novel_keys else 0.0,
        "asserted_record_count": len(records),
        "asserted_records": records,
        "assertion_label_distribution": dict(sorted(labels.items())),
        "mean_assertion_cardinality": (
            sum(len(entity["assertions"]) for _, entity in asserted) / len(asserted)
            if asserted
            else 0.0
        ),
        "external_assertion_jaccard_delta": assertion_delta,
        "observed_weighted_score_loss": weighted_loss,
        "weighted_loss_per_asserted_novel_entity": (
            weighted_loss / len(asserted) if asserted else None
        ),
        "assertion_only_isolation_surface_entities": len(asserted),
    }


def build_report(
    h23_dir: str | Path,
    h37_dir: str | Path,
    h38_dir: str | Path,
    *,
    zip_paths: dict[str, str | Path],
    expected_zip_hashes: dict[str, str],
) -> dict[str, Any]:
    actual_hashes = {name: sha256_file(path) for name, path in zip_paths.items()}
    if actual_hashes != expected_zip_hashes:
        raise ValueError(f"ZIP hash mismatch: {actual_hashes}")
    h23, h37, h38 = load_entities(h23_dir), load_entities(h37_dir), load_entities(h38_dir)
    stages = {
        "H37_vs_H23": cohort_report(h23, h37, assertion_delta=-0.1301),
        "H38_vs_H37": cohort_report(h37, h38, assertion_delta=-0.0234),
    }
    asserted_total = sum(stage["asserted_novel_entities"] for stage in stages.values())
    records = set()
    for stage in stages.values():
        records.update(stage["asserted_records"])
    weighted_loss = sum(stage["observed_weighted_score_loss"] for stage in stages.values())
    gates = {
        "both_stage_assertion_deltas_are_negative": all(
            stage["external_assertion_jaccard_delta"] < 0 for stage in stages.values()
        ),
        "at_least_20_asserted_novel_entities_total": asserted_total >= 20,
        "asserted_novel_entities_cover_at_least_15_records": len(records) >= 15,
        "combined_observed_weighted_assertion_loss_magnitude_at_least_0_10_score_points": weighted_loss >= 0.10,
        "input_zip_hashes_match": True,
    }
    return {
        "hypothesis": "H47_novel_span_assertion_leverage",
        "input_zip_hashes": actual_hashes,
        "stages": stages,
        "combined": {
            "asserted_novel_entities": asserted_total,
            "asserted_record_count": len(records),
            "observed_weighted_score_loss": weighted_loss,
            "interpretation": "evidence_leverage_not_counterfactual_upper_bound",
        },
        "gates": gates,
        "decision": "PASS_FOR_LATER_ISOLATION" if all(gates.values()) else "CLOSE_RESET_SLOT_MECHANISM",
        "artifact_policy": "NO_ALTERED_OUTPUT_OR_ZIP",
    }


def write_report(report: dict[str, Any], path: str | Path) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--h23", required=True)
    parser.add_argument("--h37", required=True)
    parser.add_argument("--h38", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = build_report(
        args.h23,
        args.h37,
        args.h38,
        zip_paths={
            "h23": "turn2/output_v8_candidate_semantic.zip",
            "h37": "turn2/output_v9_verified_symptoms.zip",
            "h38": "turn2/output_v10_multiview_consensus.zip",
        },
        expected_zip_hashes={
            "h23": "e1fc83b8e53cd9d4ac3f5d7f072a4f34eb46ee7841243a52f690ae8645514662",
            "h37": "032041a8f92bc97ca6a92d4cb4809d6aa39122471056df97bfe1fd1fe4585abc",
            "h38": "a9b9ae07997e57080ed8ce2ad9c390f4cd8c229e8eae8de447f6f47ae6ff4d0b",
        },
    )
    write_report(report, args.output)


if __name__ == "__main__":
    main()
