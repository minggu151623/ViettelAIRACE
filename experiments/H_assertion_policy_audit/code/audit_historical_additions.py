"""Classify added historical labels by independently observable section cues."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from airace.assertions import HISTORICAL_CUES, _is_historical_section
from airace.normalize import enclosing_sentence


def audit(input_dir: Path, baseline_dir: Path, candidate_dir: Path) -> dict:
    counts: Counter[str] = Counter()
    examples: defaultdict[str, list[dict]] = defaultdict(list)
    for number in range(1, 101):
        raw = (input_dir / f"{number}.txt").read_text(encoding="utf-8")
        baseline = json.loads((baseline_dir / f"{number}.json").read_text(encoding="utf-8"))
        candidate = json.loads((candidate_dir / f"{number}.json").read_text(encoding="utf-8"))
        for old, new in zip(baseline, candidate):
            if "isHistorical" in old["assertions"] or "isHistorical" not in new["assertions"]:
                continue
            start, end = new["position"]
            proxy = type("Positioned", (), {"position": (start, end)})()
            sentence = enclosing_sentence(raw, start, end).casefold()
            before = raw[:start].casefold()
            if _is_historical_section(proxy, raw):
                category = "numbered_history_section"
            elif "tiền sử bệnh hiện tại" in sentence or "bệnh sử hiện tại" in sentence:
                category = "current_history_phrase"
            elif any(cue in sentence for cue in HISTORICAL_CUES):
                category = "explicit_history_sentence"
            elif any(cue in before[-160:] for cue in HISTORICAL_CUES):
                category = "nearby_history_cue"
            else:
                category = "other"
            counts[category] += 1
            if len(examples[category]) < 5:
                examples[category].append(
                    {"file": number, "text": new["text"], "type": new["type"]}
                )
    return {"counts": dict(counts), "examples": dict(examples), "submission_artifact_written": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("input"))
    parser.add_argument("--baseline", type=Path, default=Path("output_v6_structural_btc"))
    parser.add_argument("--candidate", type=Path, default=Path("output_v11_assertion_only_btc"))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    rendered = json.dumps(audit(args.input, args.baseline, args.candidate), ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
