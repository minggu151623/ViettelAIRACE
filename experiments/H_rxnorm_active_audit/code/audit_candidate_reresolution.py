"""Read-only audit of V6 drug candidates under the current resolver.

This deliberately never writes JSON submission files.  It reports only the
candidate fields that would differ if existing V6 spans were re-resolved.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Permit direct execution from the project root without requiring an editable
# installation; this audit is intentionally a standalone, read-only tool.
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from airace.candidates import CandidateResolver
from airace.schema import Entity


def audit(input_dir: Path, baseline_dir: Path) -> dict:
    resolver = CandidateResolver()
    changes: list[dict] = []
    drug_entities = 0
    for number in range(1, 101):
        raw_text = (input_dir / f"{number}.txt").read_text(encoding="utf-8")
        values = json.loads((baseline_dir / f"{number}.json").read_text(encoding="utf-8"))
        for entity_index, value in enumerate(values):
            if value["type"] != "THUỐC":
                continue
            drug_entities += 1
            entity = Entity.from_dict(value)
            before = entity.candidates or []
            after = resolver.resolve(entity, raw_text).candidates or []
            if before != after:
                changes.append(
                    {
                        "file": number,
                        "entity_index": entity_index,
                        "text": value["text"],
                        "before": before,
                        "after": after,
                    }
                )
    return {
        "baseline": str(baseline_dir),
        "drug_entities": drug_entities,
        "candidate_changes": changes,
        "records_changed": sorted({row["file"] for row in changes}),
        "submission_artifact_written": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("input"))
    parser.add_argument("--baseline", type=Path, default=Path("output_v6_structural_btc"))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = audit(args.input, args.baseline)
    serialized = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(serialized, encoding="utf-8")
    else:
        print(serialized, end="")


if __name__ == "__main__":
    main()
