"""Train-record-only phrase/type distillation for H26."""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .proposal_pu import DEFAULT_DEV, DEFAULT_TEST, DEFAULT_TRAIN, TYPE_ORDER, _entity_key, _prf


GENERIC_HEADINGS = {
    "thuốc", "chẩn đoán", "triệu chứng", "xét nghiệm", "kết quả xét nghiệm",
    "tiền sử", "bệnh sử", "điều trị", "khám", "kết luận", "theo dõi",
}


def phrase_key(value: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value).casefold()).strip()


@dataclass(frozen=True)
class PhraseEntry:
    phrase: str
    type: str
    record_support: int
    mentions: int


@dataclass(frozen=True)
class PhraseProposal:
    record: int
    text: str
    type: str
    position: tuple[int, int]
    phrase: str
    record_support: int

    @property
    def key(self) -> tuple[int, int, str]:
        return self.position[0], self.position[1], self.type


def build_lexicon(h23_dir: str | Path, train_records: Iterable[int], min_support: int) -> list[PhraseEntry]:
    root = Path(h23_dir)
    types: dict[str, Counter[str]] = defaultdict(Counter)
    records: dict[str, set[int]] = defaultdict(set)
    mentions: Counter[str] = Counter()
    surfaces: dict[str, Counter[str]] = defaultdict(Counter)
    for record in sorted(train_records):
        values = json.loads((root / f"{record}.json").read_text(encoding="utf-8"))
        for value in values:
            text = str(value["text"])
            key = phrase_key(text)
            if (
                len(key) < 3
                or len(key.split()) > 12
                or "\n" in text
                or "\r" in text
                or not any(character.isalpha() for character in text)
                or key in GENERIC_HEADINGS
            ):
                continue
            types[key][str(value["type"])] += 1
            records[key].add(record)
            mentions[key] += 1
            surfaces[key][text] += 1
    result: list[PhraseEntry] = []
    for key, type_counts in types.items():
        if len(records[key]) < min_support or len(type_counts) != 1:
            continue
        kind = next(iter(type_counts))
        surface = min(
            surfaces[key],
            key=lambda text: (-surfaces[key][text], -len(text), text),
        )
        result.append(PhraseEntry(surface, kind, len(records[key]), mentions[key]))
    return sorted(result, key=lambda entry: (-len(entry.phrase), entry.type, phrase_key(entry.phrase)))


def _pattern(phrase: str, *, case_sensitive: bool) -> re.Pattern[str]:
    pieces = [re.escape(piece) for piece in re.split(r"\s+", phrase.strip())]
    body = r"\s+".join(pieces)
    prefix = r"(?<!\w)" if phrase[0].isalnum() else ""
    suffix = r"(?!\w)" if phrase[-1].isalnum() else ""
    return re.compile(prefix + body + suffix, 0 if case_sensitive else re.IGNORECASE)


def match_lexicon(
    raw: str,
    record: int,
    lexicon: Iterable[PhraseEntry],
    *,
    case_sensitive: bool,
) -> list[PhraseProposal]:
    result: list[PhraseProposal] = []
    seen: set[tuple[int, int, str]] = set()
    for entry in lexicon:
        for match in _pattern(entry.phrase, case_sensitive=case_sensitive).finditer(raw):
            key = (match.start(), match.end(), entry.type)
            if key in seen:
                continue
            seen.add(key)
            result.append(PhraseProposal(
                record=record,
                text=raw[match.start():match.end()],
                type=entry.type,
                position=(match.start(), match.end()),
                phrase=entry.phrase,
                record_support=entry.record_support,
            ))
    return sorted(result, key=lambda row: (row.position, row.type, row.text))


def select_disjoint(
    proposals: Iterable[PhraseProposal],
    baseline_intervals: Iterable[tuple[int, int]],
) -> list[PhraseProposal]:
    occupied = list(baseline_intervals)
    selected: list[PhraseProposal] = []
    ordered = sorted(
        proposals,
        key=lambda row: (-(row.position[1] - row.position[0]), -row.record_support,
                         row.position, row.type, row.text),
    )
    for row in ordered:
        start, end = row.position
        if any(max(start, left) < min(end, right) for left, right in occupied):
            continue
        occupied.append((start, end))
        selected.append(row)
    return sorted(selected, key=lambda row: (row.position, row.type))


def _load_keys(root: Path, record: int) -> tuple[set[tuple[int, int, str]], list[tuple[int, int]]]:
    values = json.loads((root / f"{record}.json").read_text(encoding="utf-8"))
    return {_entity_key(value) for value in values}, [tuple(value["position"]) for value in values]


def evaluate(
    input_dir: str | Path,
    h23_dir: str | Path,
    h20_dir: str | Path,
    lexicon: list[PhraseEntry],
    records: set[int],
    *,
    case_sensitive: bool,
) -> dict[str, Any]:
    inputs, h23, h20 = Path(input_dir), Path(h23_dir), Path(h20_dir)
    baseline_all: set[tuple[int, int, str, int]] = set()
    gold_all: set[tuple[int, int, str, int]] = set()
    additions_all: set[tuple[int, int, str, int]] = set()
    proposals_count = 0
    for record in sorted(records):
        raw = (inputs / f"{record}.txt").read_text(encoding="utf-8")
        gold, _ = _load_keys(h23, record)
        baseline, intervals = _load_keys(h20, record)
        proposals = match_lexicon(raw, record, lexicon, case_sensitive=case_sensitive)
        proposals_count += len(proposals)
        additions = select_disjoint(proposals, intervals)
        baseline_all.update((*key, record) for key in baseline)
        gold_all.update((*key, record) for key in gold)
        additions_all.update((*row.key, record) for row in additions)
    predicted = baseline_all | additions_all
    per_type: dict[str, Any] = {}
    for kind in TYPE_ORDER:
        baseline_kind = {key for key in baseline_all if key[2] == kind}
        predicted_kind = {key for key in predicted if key[2] == kind}
        gold_kind = {key for key in gold_all if key[2] == kind}
        per_type[kind] = {
            "baseline": _prf(baseline_kind, gold_kind),
            "with_additions": _prf(predicted_kind, gold_kind),
        }
    return {
        "case_sensitive": case_sensitive,
        "lexicon_size": len(lexicon),
        "raw_proposals": proposals_count,
        "selected_additions": len(additions_all),
        "true_additions": len(additions_all & (gold_all - baseline_all)),
        "baseline": _prf(baseline_all, gold_all),
        "with_additions": _prf(predicted, gold_all),
        "additions": _prf(additions_all, gold_all - baseline_all),
        "per_type": per_type,
    }


def run_experiment(
    input_dir: str | Path,
    h23_dir: str | Path,
    h20_dir: str | Path,
    output_dir: str | Path,
) -> dict[str, Any]:
    train, dev, test = set(DEFAULT_TRAIN), set(DEFAULT_DEV), set(DEFAULT_TEST)
    variants: list[dict[str, Any]] = []
    lexicons: dict[int, list[PhraseEntry]] = {}
    for support in (2, 3, 4):
        lexicon = build_lexicon(h23_dir, train, support)
        lexicons[support] = lexicon
        for case_sensitive in (True, False):
            result = evaluate(input_dir, h23_dir, h20_dir, lexicon, dev,
                              case_sensitive=case_sensitive)
            variants.append({"min_support": support, "dev": result})
    selected = max(
        variants,
        key=lambda item: (
            item["dev"]["with_additions"]["f1"],
            item["min_support"],
            int(item["dev"]["case_sensitive"]),
        ),
    )
    support = int(selected["min_support"])
    case_sensitive = bool(selected["dev"]["case_sensitive"])
    test_result = evaluate(input_dir, h23_dir, h20_dir, lexicons[support], test,
                           case_sensitive=case_sensitive)
    type_losses = []
    for result in (selected["dev"], test_result):
        type_losses.extend(
            100 * (metrics["with_additions"]["f1"] - metrics["baseline"]["f1"])
            for metrics in result["per_type"].values()
        )
    dev_gain = 100 * (selected["dev"]["with_additions"]["f1"] - selected["dev"]["baseline"]["f1"])
    test_gain = 100 * (test_result["with_additions"]["f1"] - test_result["baseline"]["f1"])
    gates = {
        "dev_f1_gain_at_least_3": dev_gain >= 3,
        "test_f1_gain_at_least_3": test_gain >= 3,
        "dev_addition_precision_at_least_0_75": selected["dev"]["additions"]["precision"] >= 0.75,
        "test_addition_precision_at_least_0_75": test_result["additions"]["precision"] >= 0.75,
        "no_type_loses_more_than_2": min(type_losses, default=0) >= -2,
        "dev_at_least_20_true_additions": selected["dev"]["true_additions"] >= 20,
        "test_at_least_20_true_additions": test_result["true_additions"] >= 20,
    }
    type_counts = Counter(entry.type for entry in lexicons[support])
    report = {
        "label_warning": "H23 is an externally useful pseudo target, not organizer ground truth.",
        "variants": variants,
        "selected": {
            "min_support": support,
            "case_sensitive": case_sensitive,
            "lexicon_size": len(lexicons[support]),
            "lexicon_by_type": dict(sorted(type_counts.items())),
            "dev": selected["dev"],
            "test": test_result,
        },
        "gates": gates,
        "all_gates_pass": all(gates.values()),
    }
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)
    (target / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (target / "lexicon.json").write_text(json.dumps([
        {"phrase": entry.phrase, "type": entry.type,
         "record_support": entry.record_support, "mentions": entry.mentions}
        for entry in lexicons[support]
    ], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="turn2/input")
    parser.add_argument("--h23", default="turn2/output_v8_candidate_semantic")
    parser.add_argument("--h20", default="turn2/output_v6_expanded_pair")
    parser.add_argument("--output", default="experiments/H26_phrase_policy_distillation/results")
    args = parser.parse_args()
    report = run_experiment(args.input, args.h23, args.h20, args.output)
    print(json.dumps({"selected": report["selected"], "gates": report["gates"]},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
