"""Run H66 Stage 1 generation/quality gates on the persistent T4 session."""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
REMOTE = ROOT / "stage_1_generate_remote.py"


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    cmd = ["colab", "exec", "-s", "h66", "-f", str(REMOTE), "--timeout", "2700"]
    env = os.environ.copy()
    env["PATH"] = os.path.expanduser("~/.local/bin") + os.pathsep + env.get("PATH", "")
    p = subprocess.run(cmd, text=True, capture_output=True, env=env)
    text = p.stdout + ("\nSTDERR:\n" + p.stderr if p.stderr else "")
    (RESULTS / "synthetic_terminal.log").write_text(text, encoding="utf-8")
    payload = None
    if "H66_STAGE1_JSON_BEGIN" in text and "H66_STAGE1_JSON_END" in text:
        raw = text.split("H66_STAGE1_JSON_BEGIN", 1)[1].split("H66_STAGE1_JSON_END", 1)[0].strip()
        payload = json.loads(raw)
    report = {
        "experiment": "H66_marker_preserved_translation_distillation",
        "stage": 1,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "command": cmd,
        "returncode": p.returncode,
        "remote": payload,
        "terminal_log": str(RESULTS / "synthetic_terminal.log"),
    }
    (RESULTS / "synthetic_quality_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if p.returncode == 0 and payload and payload.get("status") == "PASS_STAGE_1" else 1


if __name__ == "__main__":
    raise SystemExit(main())
