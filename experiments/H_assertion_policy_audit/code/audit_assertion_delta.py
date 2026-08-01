"""Verify that an artifact changes only assertions and quantify its scope."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def audit(baseline_dir: Path, candidate_dir: Path) -> dict:
    changed = Counter()
    changed_total = 0
    frozen_fields = True
    for number in range(1, 101):
        before = json.loads((baseline_dir / f"{number}.json").read_text(encoding="utf-8"))
        after = json.loads((candidate_dir / f"{number}.json").read_text(encoding="utf-8"))
        if len(before) != len(after):
            frozen_fields = False
            continue
        for old, new in zip(before, after):
            old_frozen = {key: value for key, value in old.items() if key != "assertions"}
            new_frozen = {key: value for key, value in new.items() if key != "assertions"}
            frozen_fields = frozen_fields and old_frozen == new_frozen
            if old["assertions"] != new["assertions"]:
                changed_total += 1
                changed[(tuple(old["assertions"]), tuple(new["assertions"]))] += 1
    return {
        "baseline": str(baseline_dir),
        "candidate": str(candidate_dir),
        "non_assertion_fields_byte_equivalent": frozen_fields,
        "assertion_rows_changed": changed_total,
        "transitions": [
            {"before": list(before), "after": list(after), "count": count}
            for (before, after), count in sorted(changed.items())
        ],
        "submission_artifact_written": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, default=Path("output_v6_structural_btc"))
    parser.add_argument("--candidate", type=Path, default=Path("output_v11_assertion_only_btc"))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = audit(args.baseline, args.candidate)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()
