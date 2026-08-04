"""Colab worker wrapper for the locked H67 Stage 1 gate."""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path("/content/h67_stage1_public")
ASSET = Path("/content/h67_stage1_public.zip")


def main() -> int:
    ROOT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(ASSET) as zf:
        zf.extractall(ROOT)
    args = [
        sys.executable,
        "/content/run_stage_1_colab.py",
        "--ontology-root", "/content/h67_stage0/ontology",
        "--public-root", str(ROOT),
        "--out", "/content/h67_stage1_report.json",
        "--alias-out", "/content/h67_stage1_aliases.jsonl",
        "--model-cache", "/content/h67_models",
    ]
    print("H67_STAGE1_ARGS", args, flush=True)
    completed = subprocess.run(args, text=True, capture_output=True)
    print("H67_STAGE1_STDOUT", completed.stdout, flush=True)
    print("H67_STAGE1_STDERR", completed.stderr, flush=True)
    print("H67_STAGE1_RESULT", completed.returncode, flush=True)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
