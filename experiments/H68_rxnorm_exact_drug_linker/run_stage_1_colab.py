"""H68 Stage 1: independent, leakage-safe RxNorm CPC supervision only.

This stage deliberately builds ingredient-family groups through all active CPC
RxNorm CUI relations, including intermediate relation-only term types. It does
not read H38 predictions, Turn2 text or ICD data, and it stops before any model
training when a locked gate fails.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


SEED = 6801
ALLOWED_TTY = {"IN", "PIN", "MIN", "SCD", "SBD", "BN", "SY", "PSN"}
RELATIONS = {
    "has_ingredient",
    "has_active_ingredient",
    "has_precise_ingredient",
    "ingredient_of",
    "precise_ingredient_of",
}


def norm(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_file(root: Path, name: str) -> Path:
    direct = root / name
    if direct.exists():
        return direct
    found = sorted(root.rglob(name))
    if not found:
        raise FileNotFoundError(name)
    return found[0]


def parse_cpc(root: Path) -> tuple[dict[str, list[str]], dict[str, str], dict[str, str], dict[str, set[str]]]:
    conso = find_file(root, "RXNCONSO.RRF")
    aliases: dict[str, list[str]] = defaultdict(list)
    alias_norms: dict[str, set[str]] = defaultdict(set)
    aui_to_cui: dict[str, str] = {}
    tty_by_cui: dict[str, str] = {}
    all_cuis: set[str] = set()
    with conso.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            cols = line.rstrip("\n").split("|")
            if len(cols) < 17 or cols[1] != "ENG" or cols[11] not in {"RXNORM", "MTHSPL"}:
                continue
            if cols[16] not in {"", "N"}:
                continue
            cui, aui, tty, text = cols[0], cols[7], cols[12], cols[14].strip()
            if not cui or not aui:
                continue
            all_cuis.add(cui)
            aui_to_cui[aui] = cui
            tty_by_cui.setdefault(cui, tty)
            text_norm = norm(text)
            if tty in ALLOWED_TTY and text and text_norm not in alias_norms[cui]:
                aliases[cui].append(text)
                alias_norms[cui].add(text_norm)
    parent = {cui: cui for cui in all_cuis}

    def find(cui: str) -> str:
        while parent[cui] != cui:
            parent[cui] = parent[parent[cui]]
            cui = parent[cui]
        return cui

    def union(left: str, right: str) -> None:
        left, right = find(left), find(right)
        if left != right:
            parent[right] = left

    rel = find_file(root, "RXNREL.RRF")
    relation_rows = 0
    with rel.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            cols = line.rstrip("\n").split("|")
            if len(cols) < 11 or cols[7] not in RELATIONS:
                continue
            left, right = aui_to_cui.get(cols[1]), aui_to_cui.get(cols[5])
            if left in parent and right in parent and left != right:
                union(left, right)
                relation_rows += 1
    family = {cui: "rxfamily:" + find(cui) for cui in aliases}
    aliases = {cui: sorted(values, key=lambda x: (norm(x), x)) for cui, values in aliases.items()}
    family_members: dict[str, set[str]] = defaultdict(set)
    for cui in aliases:
        family_members[find(cui)].add(cui)
    return aliases, family, tty_by_cui, family_members


def split_families(families: set[str]) -> dict[str, str]:
    ordered = sorted(families)
    random.Random(SEED).shuffle(ordered)
    cut1, cut2 = int(len(ordered) * 0.70), int(len(ordered) * 0.85)
    return {family: ("train" if i < cut1 else "dev" if i < cut2 else "test") for i, family in enumerate(ordered)}


def iter_public_sentences(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts or path.name.lower().startswith("readme"):
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            continue
        tokens: list[str] = []
        index = 0
        for line in lines + [""]:
            if not line.strip():
                if tokens:
                    yield f"{path.name}:{index}", norm(" ".join(tokens))
                    index += 1
                    tokens = []
                continue
            cols = line.split()
            tokens.append(cols[0] if len(cols) >= 2 else line.strip())


def public_anchors(root: Path, aliases: dict[str, list[str]]) -> dict[str, object]:
    alias_to_codes: dict[str, set[str]] = defaultdict(set)
    for cui, values in aliases.items():
        for value in values:
            alias_to_codes[norm(value)].add(cui)
    patterns: dict[str, list[tuple[tuple[str, ...], str]]] = defaultdict(list)
    for alias, codes in alias_to_codes.items():
        if len(codes) == 1 and alias:
            tokens = tuple(alias.split())
            patterns[tokens[0]].append((tokens, next(iter(codes))))
    anchors: set[tuple[str, str, str]] = set()
    for sid, sentence in iter_public_sentences(root):
        tokens = sentence.split()
        for i, token in enumerate(tokens):
            for pattern, cui in patterns.get(token, []):
                if tuple(tokens[i : i + len(pattern)]) == pattern:
                    anchors.add((sid, " ".join(pattern), cui))
    return {"count": len(anchors), "unique_passages": len({x[0] for x in anchors}), "sample": sorted(anchors)[:20]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rxnorm-root", type=Path, required=True)
    ap.add_argument("--public-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--alias-out", type=Path, required=True)
    args = ap.parse_args()
    started = time.time()
    report: dict[str, object] = {
        "hypothesis": "H68_rxnorm_exact_drug_linker",
        "stage": "stage_1_independent_rxnorm_dataset",
        "protocol": "locked",
        "seed": SEED,
        "errors": [],
    }
    try:
        aliases, family_by_cui, tty_by_cui, family_members = parse_cpc(args.rxnorm_root)
        rows = [
            {"ontology": "RXNORM", "code": cui, "text": text, "family": family_by_cui[cui]}
            for cui, values in aliases.items()
            for text in values
        ]
        split = split_families(set(family_by_cui.values()))
        for row in rows:
            row["split"] = split[row["family"]]
        normalized: dict[str, set[str]] = defaultdict(set)
        for row in rows:
            normalized[norm(row["text"])].add(row["code"])
        collisions = {key for key, codes in normalized.items() if len(codes) > 1}
        anchors = public_anchors(args.public_root, aliases)
        family_count = len(set(family_by_cui.values()))
        report["checks"] = {
            "rxnorm_alias_quality": {
                "active_codes": len(aliases),
                "accepted_same_code_alias_pairs": len(rows),
                "ingredient_families": family_count,
                "relation_connected_family_members": len(family_members),
                "tty_counts": dict(Counter(tty_by_cui[cui] for cui in aliases)),
            },
            "family_split": {
                "train": sum(v == "train" for v in split.values()),
                "dev": sum(v == "dev" for v in split.values()),
                "test": sum(v == "test" for v in split.values()),
                "overlap": 0,
                "seed": SEED,
            },
            "alias_collision": {
                "normalized_aliases": len(normalized),
                "cross_code_collisions": len(collisions),
                "collision_rate": len(collisions) / max(1, len(normalized)),
            },
            "public_context_anchor": anchors,
        }
        gates = {
            "accepted_same_code_alias_pairs_ge_50000": len(rows) >= 50000,
            "ingredient_families_ge_30000": family_count >= 30000,
            "family_overlap_equals_zero": True,
            "collision_rate_le_0.002": report["checks"]["alias_collision"]["collision_rate"] <= 0.002,
            "public_unique_rxnorm_context_anchors_ge_300": anchors["count"] >= 300,
        }
        report["gates"] = gates
        if not all(gates.values()):
            raise RuntimeError("H68 Stage 1 independent RxNorm gate failed")
        args.alias_out.parent.mkdir(parents=True, exist_ok=True)
        with args.alias_out.open("w", encoding="utf-8") as f:
            for row in rows:
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        report["status"] = "PASS_STAGE_1"
    except Exception as exc:
        report["status"] = "FAIL_STAGE_1"
        report.setdefault("errors", []).append(f"{type(exc).__name__}: {exc}")
    finally:
        report["elapsed_seconds"] = round(time.time() - started, 3)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
        print(json.dumps({"status": report.get("status"), "elapsed_seconds": report["elapsed_seconds"], "errors": report["errors"], "gates": report.get("gates")}, ensure_ascii=False), flush=True)
    return 0 if report.get("status") == "PASS_STAGE_1" else 2


if __name__ == "__main__":
    raise SystemExit(main())
