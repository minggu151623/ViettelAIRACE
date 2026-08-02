"""Read-only independent agreement audit for frozen H34 predictions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .normalize import normalize_key
from .phrase_policy import build_lexicon, match_lexicon, select_disjoint
from .proposal_pu import DEFAULT_DEV, DEFAULT_TEST, DEFAULT_TRAIN
from .proposals import load_proposals


KNOWN_HAZARDS = {normalize_key(value) for value in
                 ("doxycyclinebactrim", "klonopinclonidine", "ảo giácxuất", "buồn", "đoạn")}


def key(row: dict[str, Any]) -> tuple[int, int, str, int]:
    return (int(row["position"][0]), int(row["position"][1]),
            str(row["type"]), int(row["record"]))


def audit_agreement(predictions: str | Path, input_dir: str | Path,
                    h23_dir: str | Path, h20_dir: str | Path,
                    vietmed_dir: str | Path) -> dict[str, Any]:
    rows = json.loads(Path(predictions).read_text(encoding="utf-8"))
    h34 = {key(row): row for row in rows}
    h23 = set()
    vietmed = set()
    phrase = set()
    lexicon = build_lexicon(h23_dir, DEFAULT_TRAIN, 2)
    phrase_records = set(DEFAULT_DEV) | set(DEFAULT_TEST)
    for record in range(1, 101):
        raw = (Path(input_dir) / f"{record}.txt").read_text(encoding="utf-8")
        for entity in json.loads((Path(h23_dir) / f"{record}.json").read_text(encoding="utf-8")):
            h23.add((entity["position"][0], entity["position"][1], entity["type"], record))
        vietmed.update((item.position[0], item.position[1], item.type, record)
                       for item in load_proposals(Path(vietmed_dir) / f"{record}.json"))
        if record in phrase_records:
            baseline = json.loads((Path(h20_dir) / f"{record}.json").read_text(encoding="utf-8"))
            selected = select_disjoint(
                match_lexicon(raw, record, lexicon, case_sensitive=False),
                [tuple(entity["position"]) for entity in baseline],
            )
            phrase.update((item.position[0], item.position[1], item.type, record)
                          for item in selected)
    novel = set(h34) - h23
    tier_a = novel & vietmed
    tier_b = novel & phrase
    both = tier_a & tier_b
    queue = []
    for item in sorted(tier_a | tier_b, key=lambda value: (value[3], value[0], value[1], value[2])):
        row = h34[item]
        raw = (Path(input_dir) / f"{item[3]}.txt").read_text(encoding="utf-8")
        start, end = item[0], item[1]
        queue.append({**row, "tier_A_vietmed": item in tier_a,
                      "tier_B_phrase_heldout": item in tier_b,
                      "known_hazard": normalize_key(row["text"]) in KNOWN_HAZARDS,
                      "context": raw[max(0, start - 120):min(len(raw), end + 120)]})
    return {"h34_predictions": len(h34), "h34_novel": len(novel),
            "tier_A_vietmed": len(tier_a), "tier_B_phrase_heldout": len(tier_b),
            "both_sources": len(both),
            "known_hazards_in_queue": sum(row["known_hazard"] for row in queue),
            "queue": queue}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictions", default="experiments/H34_minimum_epoch_recovery/results/combined_oof_predictions.json")
    parser.add_argument("--input", default="turn2/input")
    parser.add_argument("--h23", default="turn2/output_v8_candidate_semantic")
    parser.add_argument("--h20", default="turn2/output_v6_expanded_pair")
    parser.add_argument("--vietmed", default="experiments/H_turn2_multimodel_core/proposals_vietmed")
    parser.add_argument("--output", default="experiments/H35_independent_agreement_audit/results")
    args = parser.parse_args()
    result = audit_agreement(args.predictions, args.input, args.h23, args.h20, args.vietmed)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "report.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "queue"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
