"""Colab worker wrapper: unpack the immutable Stage 0 asset bundle then run gate."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path("/content/h67_stage0")
ASSET = Path("/content/h67_stage0_assets.zip")


def main() -> int:
    ROOT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ASSET) as zf:
        zf.extractall(ROOT)
    baseline = ROOT / "baseline"
    input_dir = ROOT / "input"
    ontology = ROOT / "ontology"
    who = ontology / "who"
    rxnorm = ontology / "rxnorm"
    who.mkdir(exist_ok=True)
    rxnorm.mkdir(exist_ok=True)
    with zipfile.ZipFile(ontology / "who_icd102019.zip") as zf:
        zf.extractall(who)
    with zipfile.ZipFile(ontology / "rxnorm_cpc.zip") as zf:
        zf.extractall(rxnorm)
    # The CPC archive places RRF files below a nested directory on some
    # releases; make the runner's contract independent of that layout.
    nested = list(rxnorm.rglob("RXNCONSO.RRF"))
    if nested and nested[0].parent != rxnorm:
        for p in nested[0].parent.iterdir():
            target = rxnorm / p.name
            if not target.exists():
                p.rename(target)
    args = [
        sys.executable,
        "/content/run_stage_0_colab.py",
        "--baseline-zip", str(baseline / "h38.zip"),
        "--baseline-dir", str(baseline),
        "--input-dir", str(input_dir),
        "--graph-manifest", str(ontology / "graph_manifest.json"),
        "--resource-manifest", str(ontology / "resource_manifest.json"),
        "--who-dir", str(who),
        "--rxnorm-dir", str(rxnorm),
        # Use a fresh path so an earlier queued kernel execution cannot make
        # a stale report look like the current run.
        "--out", "/content/h67_stage0_report_fixed.json",
    ]
    return subprocess.call(args)


if __name__ == "__main__":
    raise SystemExit(main())
