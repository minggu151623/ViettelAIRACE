"""H68 Stage 0 Colab wrapper.

The H67 runner already contains the audited baseline/resource/CUDA smoke checks.
This wrapper reuses only that integrity implementation, adds the H68 drug census
gate, and rewrites the report identity to H68. It is intentionally fail-closed.
"""

from __future__ import annotations

import json
import subprocess
import sys
import zipfile
from pathlib import Path


ROOT = Path("/content/h68_stage0")
ASSET = Path("/content/h68_stage0_assets.zip")
REPORT = Path("/content/h68_stage0_report.json")


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
        "--baseline-dir", str(baseline / "h38_dir"),
        "--input-dir", str(input_dir),
        "--graph-manifest", str(ontology / "graph_manifest.json"),
        "--resource-manifest", str(ontology / "resource_manifest.json"),
        "--who-dir", str(who),
        "--rxnorm-dir", str(rxnorm),
        "--out", "/content/h68_h67_integrity_report.json",
    ]
    completed = subprocess.run(args, text=True, capture_output=True)
    print(completed.stdout, flush=True)
    print(completed.stderr, flush=True)
    report = json.loads(Path("/content/h68_h67_integrity_report.json").read_text(encoding="utf-8"))
    report["hypothesis"] = "H68_rxnorm_exact_drug_linker"
    report["stage"] = "stage_0_reproducibility_and_runtime"
    report["h67_integrity_returncode"] = completed.returncode
    drug_total = nonempty = empty = 0
    for p in sorted((baseline / "h38_dir").glob("*.json"), key=lambda q: int(q.stem)):
        rows = json.loads(p.read_text(encoding="utf-8"))
        for row in rows:
            if row.get("type") != "THUỐC":
                continue
            drug_total += 1
            if row.get("candidates"):
                nonempty += 1
            else:
                empty += 1
    census_ok = (drug_total, nonempty, empty) == (276, 201, 75)
    report.setdefault("checks", {})["h68_drug_census"] = {
        "ok": census_ok,
        "observed": {"total": drug_total, "nonempty": nonempty, "empty": empty},
        "expected": {"total": 276, "nonempty": 201, "empty": 75},
    }
    base_pass = report.get("status") == "PASS_STAGE_0"
    report["status"] = "PASS_STAGE_0" if base_pass and census_ok else "FAIL_STAGE_0"
    if not census_ok:
        report.setdefault("errors", []).append("H68 drug census mismatch")
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "drug_census": [drug_total, nonempty, empty]}, ensure_ascii=False), flush=True)
    return 0 if report["status"] == "PASS_STAGE_0" else 2


if __name__ == "__main__":
    raise SystemExit(main())
