"""Deterministic exposure concentration audit for H23 and H44."""

from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


def normalize_mention(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _inverse_simpson(counter: Counter[Any]) -> float:
    total = sum(counter.values())
    return 0.0 if not total else 1.0 / sum((count / total) ** 2 for count in counter.values())


def _top_share(counter: Counter[Any], k: int) -> float:
    total = sum(counter.values())
    return 0.0 if not total else sum(sorted(counter.values(), reverse=True)[:k]) / total


def _canonical_change(change: dict[str, Any]) -> tuple[str, str, str, str]:
    record = str(change.get("record_id", change.get("record")))
    candidates = change.get("after", change.get("new_candidates"))
    if not isinstance(candidates, list) or len(candidates) != 2:
        raise ValueError("every audited change must have exactly two post-change candidates")
    parent, specific = map(str, candidates)
    if not specific.replace(".", "").startswith(parent.replace(".", "")):
        raise ValueError(f"candidate pair is not same-family: {candidates!r}")
    return record, normalize_mention(str(change["text"])), parent, specific


def summarize(changes: Iterable[dict[str, Any]]) -> dict[str, Any]:
    source_changes = list(changes)
    rows = [_canonical_change(change) for change in source_changes]
    records = Counter(row[0] for row in rows)
    parents = Counter(row[2] for row in rows)
    specifics = Counter(row[3] for row in rows)
    lexical = Counter((row[1], row[3]) for row in rows)
    return {
        "changed_rows": len(rows),
        "affected_records": len(records),
        "unique_parent_families": len(parents),
        "unique_specific_codes": len(specifics),
        "unique_lexical_units": len(lexical),
        "effective_parent_families_inverse_simpson": round(_inverse_simpson(parents), 6),
        "effective_specific_codes_inverse_simpson": round(_inverse_simpson(specifics), 6),
        "effective_lexical_units_inverse_simpson": round(_inverse_simpson(lexical), 6),
        "top_1_parent_row_share": round(_top_share(parents, 1), 6),
        "top_5_parent_row_share": round(_top_share(parents, 5), 6),
        "top_10_lexical_unit_row_share": round(_top_share(lexical, 10), 6),
        "diagnostic_casefold_only_unique_lexical_units": len(
            {
                (str(change["text"]).casefold(), _canonical_change(change)[3])
                for change in source_changes
            }
        ),
        "parent_families": sorted(parents),
        "specific_codes": sorted(specifics),
        "lexical_units": sorted([list(key) for key in lexical]),
        "top_parent_counts": [[key, value] for key, value in parents.most_common(10)],
        "top_lexical_unit_counts": [
            [[mention, code], value] for (mention, code), value in lexical.most_common(10)
        ],
    }


def concentration_audit(h23: dict[str, Any], h44: dict[str, Any]) -> dict[str, Any]:
    summaries = {"H23": summarize(h23["changes"]), "H44": summarize(h44["changes"])}
    h23_summary, h44_summary = summaries["H23"], summaries["H44"]
    family_broad = (
        h44_summary["unique_parent_families"] >= 20
        and h44_summary["effective_parent_families_inverse_simpson"] >= 20
        and h44_summary["top_5_parent_row_share"] <= 0.50
    )
    lexical_broad = (
        h44_summary["effective_lexical_units_inverse_simpson"] >= 100
        and h44_summary["top_10_lexical_unit_row_share"] <= 0.25
    )
    if family_broad and lexical_broad:
        interpretation = "both_broad"
    elif family_broad:
        interpretation = "family_only"
    elif lexical_broad:
        interpretation = "lexical_only"
    else:
        interpretation = "neither_broad"
    cross = {
        "parent_family_overlap": len(set(h23_summary["parent_families"]) & set(h44_summary["parent_families"])),
        "specific_code_overlap": len(set(h23_summary["specific_codes"]) & set(h44_summary["specific_codes"])),
        "lexical_unit_overlap": len(
            {tuple(x) for x in h23_summary["lexical_units"]}
            & {tuple(x) for x in h44_summary["lexical_units"]}
        ),
    }
    return {
        "hypothesis": "H53_h44_exposure_concentration",
        "summaries": summaries,
        "cross_experiment": cross,
        "gates": {
            "broad_family_exposure": family_broad,
            "broad_lexical_exposure": lexical_broad,
            "reproducibility": True,
        },
        "interpretation": interpretation,
    }


def write_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--h23", type=Path, required=True)
    parser.add_argument("--h44", type=Path, required=True)
    parser.add_argument("--h44-zip", type=Path, required=True)
    parser.add_argument("--expected-h44-zip-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    actual_hash = sha256(args.h44_zip)
    if actual_hash != args.expected_h44_zip_sha256:
        raise SystemExit(f"H44 ZIP hash mismatch: {actual_hash}")
    h23 = json.loads(args.h23.read_text())
    h44 = json.loads(args.h44.read_text())
    if len(h23["changes"]) != 144 or len(h44["changes"]) != 611:
        raise SystemExit("frozen input row counts do not match H23=144 and H44=611")
    report = concentration_audit(h23, h44)
    report["h44_zip_sha256"] = actual_hash
    write_report(report, args.output)


if __name__ == "__main__":
    main()
