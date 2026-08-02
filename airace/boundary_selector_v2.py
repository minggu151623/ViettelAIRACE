"""Coverage-complete token boundary selector for H29."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

from .boundary_selector import (
    ALLOWED_TYPES,
    _corrupt_seed,
    _entity_tokens,
    _trim,
    evaluate,
    review_cases,
    test_gates,
)
from .proposal_pu import DEFAULT_DEV, DEFAULT_TEST


def enumerate_choices_v2(
    raw: str,
    seed: tuple[int, int],
    *,
    max_tokens: int = 10,
    max_left: int = 7,
    max_right: int = 7,
) -> list[dict[str, Any]]:
    seed_start, seed_end = seed
    line_start = raw.rfind("\n", 0, seed_start) + 1
    line_end = raw.find("\n", seed_end)
    if line_end < 0:
        line_end = len(raw)
    tokens = [(line_start + match.start(), line_start + match.end())
              for match in re.finditer(r"\S+", raw[line_start:line_end])]
    overlapping = [index for index, (start, end) in enumerate(tokens)
                   if start < seed_end and end > seed_start]
    if not overlapping:
        return [{"choice_id": 0, "text": raw[seed_start:seed_end],
                 "position": [seed_start, seed_end]}]
    first, last = overlapping[0], overlapping[-1]
    values: dict[tuple[int, int], dict[str, Any]] = {}
    for left in range(max(0, first - max_left), first + 1):
        for right in range(last, min(len(tokens) - 1, last + max_right) + 1):
            if right - left + 1 > max_tokens:
                continue
            variants = [
                (tokens[left][0], tokens[right][1]),
                _trim(raw, tokens[left][0], tokens[right][1]),
            ]
            for start, end in variants:
                if start <= seed_start and end >= seed_end and start < end:
                    values[(start, end)] = {"text": raw[start:end],
                                            "position": [start, end]}
    values[(seed_start, seed_end)] = {"text": raw[seed_start:seed_end],
                                      "position": [seed_start, seed_end]}
    ordered = sorted(
        values.values(),
        key=lambda item: (
            abs(item["position"][0] - seed_start) + abs(item["position"][1] - seed_end),
            item["position"][1] - item["position"][0],
            item["position"],
        ),
    )
    return [{"choice_id": index, **item} for index, item in enumerate(ordered)]


def build_cases_v2(input_dir: str | Path, target_dir: str | Path,
                   records: Iterable[int]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    inputs, targets = Path(input_dir), Path(target_dir)
    cases: list[dict[str, Any]] = []
    candidate_entities = eligible = excluded = covered = 0
    for record in sorted(records):
        raw = (inputs / f"{record}.txt").read_text(encoding="utf-8")
        entities = json.loads((targets / f"{record}.json").read_text(encoding="utf-8"))
        for entity in entities:
            if entity["type"] not in ALLOWED_TYPES:
                continue
            gold = tuple(entity["position"])
            tokens = _entity_tokens(raw, *gold)
            if not 2 <= len(tokens) <= 8:
                continue
            candidate_entities += 1
            seed = _corrupt_seed(record, entity, tokens)
            choices = enumerate_choices_v2(raw, seed)
            if gold not in {tuple(choice["position"]) for choice in choices}:
                excluded += 1
                continue
            eligible += 1
            covered += 1
            line_start = raw.rfind("\n", 0, seed[0]) + 1
            line_end = raw.find("\n", seed[1])
            if line_end < 0:
                line_end = len(raw)
            for mode, active_seed in (("corrupted", seed), ("control", gold)):
                active_choices = enumerate_choices_v2(raw, active_seed)
                cases.append({
                    "id": len(cases), "record": record, "mode": mode,
                    "type": entity["type"], "seed": list(active_seed),
                    "seed_text": raw[active_seed[0]:active_seed[1]],
                    "gold": list(gold), "gold_text": raw[gold[0]:gold[1]],
                    "context": raw[line_start:active_seed[0]] + "⟦" + raw[active_seed[0]:active_seed[1]] + "⟧" + raw[active_seed[1]:line_end],
                    "choices": active_choices,
                })
    return cases, {
        "candidate_entities": candidate_entities,
        "excluded_unrepresentable": excluded,
        "eligible_entities": eligible,
        "covered_entities": covered,
        "coverage": covered / eligible if eligible else 1.0,
    }


def dev_gates_v2(result: dict[str, Any]) -> dict[str, bool]:
    return {
        "eligible_enumerator_coverage_equals_1": result["enumeration"]["coverage"] == 1.0,
        "corrupted_exact_recovery_at_least_0_70": result["corrupted_exact_recovery"] >= 0.70,
        "unchanged_control_retention_at_least_0_93": result["unchanged_control_retention"] >= 0.93,
        "malformed_response_rate_equals_0": result["malformed_response_rate"] == 0,
    }


def run_experiment(input_dir: str | Path, target_dir: str | Path,
                   output_dir: str | Path) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    dev_cases, dev_enumeration = build_cases_v2(input_dir, target_dir, DEFAULT_DEV)
    dev_review = review_cases(dev_cases, output / "dev_review.json")
    dev = evaluate(dev_review, dev_enumeration)
    gates = dev_gates_v2(dev)
    report: dict[str, Any] = {"dev": dev, "dev_gates": gates, "test": None,
                             "test_gates": None, "status": "dev_failed_test_canceled"}
    if all(gates.values()):
        test_cases, test_enumeration = build_cases_v2(input_dir, target_dir, DEFAULT_TEST)
        path = output / "test_review.json"
        test_review = review_cases(test_cases, path)
        first = path.read_bytes()
        review_cases(test_cases, path)
        second = path.read_bytes()
        test = evaluate(test_review, test_enumeration)
        final = test_gates(test, first.hex(), second.hex())
        report.update({"test": test, "test_gates": final,
                       "status": "passed" if all(final.values()) else "test_failed"})
    (output / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="turn2/input")
    parser.add_argument("--target", default="turn2/output_v8_candidate_semantic")
    parser.add_argument("--output", default="experiments/H29_token_aligned_boundary_selector/results")
    args = parser.parse_args()
    print(json.dumps(run_experiment(args.input, args.target, args.output),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
