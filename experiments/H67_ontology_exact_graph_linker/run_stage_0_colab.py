"""H67 Stage 0 integrity/resource gate for the Colab T4 worker.

This runner is deliberately fail-closed.  It does not train a linker or
modify Turn2.  It verifies the frozen H38 artifact, validates all 100 JSON
records against the submitted input, records ontology manifests, and runs a
small forward/backward memory smoke test for the two models required by the
locked H67 protocol.

The script is self-contained so it can be uploaded to a fresh Colab session;
the local runner downloads only the resulting JSON report.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import re
import subprocess
import sys
import time
import zipfile
from pathlib import Path
from typing import Any


EXPECTED_H38 = "a9b9ae07997e57080ed8ce2ad9c390f4cd8c229e8eae8de447f6f47ae6ff4d0b"
EXPECTED_N = 100
VALID_TYPES = {
    "CHẨN_ĐOÁN",
    "TRIỆU_CHỨNG",
    "TÊN_XÉT_NGHIỆM",
    "KẾT_QUẢ_XÉT_NGHIỆM",
    "THUỐC",
    "THÔNG_TIN_BỆNH_NHÂN",
}
VALID_ASSERTIONS = {"isNegated", "isHistorical", "isFamily"}
CANDIDATE_TYPES = {"CHẨN_ĐOÁN", "THUỐC"}


def sha256(path: Path, chunk: int = 8 * 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                return h.hexdigest()
            h.update(b)


def ensure_import(name: str, package: str | None = None) -> None:
    if importlib.util.find_spec(name) is not None:
        return
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", package or name])


def validate_record(input_text: str, rows: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(rows, list):
        return ["record is not a JSON list"]
    prev: tuple[int, int] | None = None
    seen: set[tuple[int, int, str]] = set()
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"row {i}: not an object")
            continue
        for key in ("text", "type", "assertions", "position"):
            if key not in row:
                errors.append(f"row {i}: missing {key}")
        typ = row.get("type")
        if typ not in VALID_TYPES:
            errors.append(f"row {i}: invalid type {typ!r}")
        assertions = row.get("assertions")
        if not isinstance(assertions, list) or any(a not in VALID_ASSERTIONS for a in assertions):
            errors.append(f"row {i}: invalid assertions")
        pos = row.get("position")
        if not isinstance(pos, list) or len(pos) != 2 or not all(isinstance(x, int) for x in pos):
            errors.append(f"row {i}: invalid position")
            continue
        start, end = pos
        if start < 0 or end < start or end > len(input_text):
            errors.append(f"row {i}: position out of bounds {pos}")
        elif row.get("text") != input_text[start:end]:
            errors.append(f"row {i}: text/offset mismatch")
        key = (start, end, str(typ))
        if key in seen:
            errors.append(f"row {i}: duplicate entity")
        seen.add(key)
        if prev is not None and (start, end) < prev:
            errors.append(f"row {i}: entities not sorted")
        prev = (start, end)
        if typ not in CANDIDATE_TYPES and "candidates" in row and row.get("candidates") not in (None, []):
            errors.append(f"row {i}: noncandidate has candidates")
        if typ in CANDIDATE_TYPES and "candidates" in row:
            cand = row.get("candidates")
            if not isinstance(cand, list) or any(not isinstance(c, str) or not c for c in cand):
                errors.append(f"row {i}: malformed candidates")
    return errors


def model_smoke_test(report: dict[str, Any], model_root: Path) -> None:
    """Run the two locked T4 smoke tests and record enough detail to audit."""
    ensure_import("torch")
    ensure_import("transformers")
    import torch  # type: ignore
    from transformers import AutoModel, AutoModelForSequenceClassification, AutoTokenizer  # type: ignore

    report["gpu"] = {
        "cuda_available": bool(torch.cuda.is_available()),
        "device_count": int(torch.cuda.device_count()),
        "device_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "torch": torch.__version__,
    }
    if not torch.cuda.is_available():
        raise RuntimeError("H67 Stage 0 requires CUDA/T4; no CUDA device is visible")
    device = torch.device("cuda:0")
    dtype = torch.float16

    qwen_id = "Qwen/Qwen3-Embedding-0.6B"
    qwen_t0 = time.time()
    qtok = AutoTokenizer.from_pretrained(qwen_id, cache_dir=str(model_root), trust_remote_code=True)
    qmodel = AutoModel.from_pretrained(
        qwen_id, cache_dir=str(model_root), trust_remote_code=True, torch_dtype=dtype
    ).to(device)
    qmodel.train()
    qinputs = qtok(
        ["thiếu máu tán huyết", "hemolytic anemia"],
        padding=True,
        truncation=True,
        max_length=64,
        return_tensors="pt",
    )
    qinputs = {k: v.to(device) for k, v in qinputs.items()}
    qout = qmodel(**qinputs)
    qhidden = getattr(qout, "last_hidden_state", None)
    if qhidden is None:
        raise RuntimeError("Qwen embedding model did not expose last_hidden_state")
    qmask = qinputs["attention_mask"].unsqueeze(-1).to(qhidden.dtype)
    qemb = (qhidden * qmask).sum(1) / qmask.sum(1).clamp_min(1)
    qloss = qemb.float().pow(2).mean()
    qloss.backward()
    qmodel.zero_grad(set_to_none=True)
    report["qwen_embedding"] = {
        "model": qwen_id,
        "hidden_size": int(qemb.shape[-1]),
        "batch": int(qemb.shape[0]),
        "forward_backward": True,
        "seconds": round(time.time() - qwen_t0, 3),
    }
    del qmodel, qtok, qout, qhidden, qemb, qinputs
    torch.cuda.empty_cache()

    xlm_id = "xlm-roberta-base"
    xlm_t0 = time.time()
    xtok = AutoTokenizer.from_pretrained(xlm_id, cache_dir=str(model_root))
    xmodel = AutoModelForSequenceClassification.from_pretrained(
        xlm_id, num_labels=2, cache_dir=str(model_root), torch_dtype=dtype
    ).to(device)
    xmodel.train()
    xinputs = xtok(
        ["bệnh dại", "thiếu máu"],
        ["rabies", "anemia"],
        padding=True,
        truncation=True,
        max_length=128,
        return_tensors="pt",
    )
    xinputs = {k: v.to(device) for k, v in xinputs.items()}
    labels = torch.tensor([1, 0], device=device)
    xout = xmodel(**xinputs, labels=labels)
    xout.loss.backward()
    xmodel.zero_grad(set_to_none=True)
    report["xlm_roberta_pair"] = {
        "model": xlm_id,
        "batch": 2,
        "required_batch_minimum": 8,
        "probe_batch_fit": True,
        "seconds": round(time.time() - xlm_t0, 3),
    }
    # A separate batch=8 forward/backward is the locked fit criterion.
    xinputs8 = xtok(
        ["bệnh dại"] * 8,
        ["rabies"] * 8,
        padding=True,
        truncation=True,
        max_length=128,
        return_tensors="pt",
    )
    xinputs8 = {k: v.to(device) for k, v in xinputs8.items()}
    labels8 = torch.zeros(8, dtype=torch.long, device=device)
    xout8 = xmodel(**xinputs8, labels=labels8)
    xout8.loss.backward()
    report["xlm_roberta_pair"]["batch_8_forward_backward"] = True
    del xmodel, xtok, xout, xout8, xinputs, xinputs8
    torch.cuda.empty_cache()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline-zip", type=Path, required=True)
    ap.add_argument("--baseline-dir", type=Path, required=True)
    ap.add_argument("--input-dir", type=Path, required=True)
    ap.add_argument("--graph-manifest", type=Path, required=True)
    ap.add_argument("--resource-manifest", type=Path, required=True)
    ap.add_argument("--who-dir", type=Path, required=True)
    ap.add_argument("--rxnorm-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--model-cache", type=Path, default=Path("/content/h67_models"))
    args = ap.parse_args()
    started = time.time()
    report: dict[str, Any] = {
        "hypothesis": "H67_ontology_exact_graph_linker",
        "stage": "stage_0_integrity_and_resource_manifest",
        "protocol": "locked",
        "started_unix": started,
        "host": {"platform": platform.platform(), "python": sys.version},
        "checks": {},
        "errors": [],
    }

    try:
        if sha256(args.baseline_zip) != EXPECTED_H38:
            raise RuntimeError("frozen H38 ZIP SHA256 mismatch")
        report["checks"]["baseline_sha256"] = {"ok": True, "sha256": EXPECTED_H38}

        json_files = sorted(args.baseline_dir.glob("*.json"), key=lambda p: int(p.stem) if p.stem.isdigit() else 10**9)
        if len(json_files) != EXPECTED_N or {p.stem for p in json_files} != {str(i) for i in range(1, 101)}:
            raise RuntimeError(f"expected exactly 1.json..100.json, got {len(json_files)} files")
        validation_errors: dict[str, list[str]] = {}
        for p in json_files:
            # Turn2 input is 1.txt..100.txt while the output artifact is
            # 1.json..100.json; pairing by numeric stem is part of the
            # immutable submission contract.
            ip = args.input_dir / f"{p.stem}.txt"
            if not ip.exists():
                ip = args.input_dir / p.name
            raw = ip.read_text(encoding="utf-8")
            errs = validate_record(raw, json.loads(p.read_text(encoding="utf-8")))
            if errs:
                validation_errors[p.name] = errs
        report["checks"]["baseline_100_json"] = {
            "ok": not validation_errors,
            "count": len(json_files),
            "errors": validation_errors,
        }
        if validation_errors:
            raise RuntimeError(f"H38 validation failed in {len(validation_errors)} records")

        graph = json.loads(args.graph_manifest.read_text(encoding="utf-8"))
        graph_ok = bool(
            graph.get("nodes", 0) >= 69000
            and graph.get("edges", 0) >= 290000
            and re.fullmatch(r"[0-9a-f]{64}", graph.get("node_sha256", ""))
            and re.fullmatch(r"[0-9a-f]{64}", graph.get("edge_sha256", ""))
        )
        report["checks"]["graph_manifest"] = {
            "ok": graph_ok,
            "sha256": sha256(args.graph_manifest),
            "manifest": graph,
        }
        if not graph_ok:
            raise RuntimeError("graph manifest count/hash fields failed")

        resource = json.loads(args.resource_manifest.read_text(encoding="utf-8"))
        who_files = sorted(args.who_dir.rglob("*"))
        rx_files = sorted(args.rxnorm_dir.rglob("*"))
        rx_rrf = [p for p in rx_files if p.name == "RXNCONSO.RRF"]
        rx_readable = bool(rx_rrf and rx_rrf[0].stat().st_size > 1000)
        who_readable = any(p.suffix.lower() in {".txt", ".zip"} and p.stat().st_size > 1000 for p in who_files)
        report["checks"]["ontology_snapshots"] = {
            "ok": bool(who_readable and rx_readable),
            "who_files": [{"path": str(p), "bytes": p.stat().st_size, "sha256": sha256(p)} for p in who_files if p.is_file()],
            "rxnorm_files": [{"path": str(p), "bytes": p.stat().st_size, "sha256": sha256(p)} for p in rx_files if p.is_file() and p.stat().st_size < 1_500_000_000],
            "resource_manifest": resource,
        }
        if not (who_readable and rx_readable):
            raise RuntimeError("WHO ICD-10 or RxNorm CPC snapshot is unreadable")

        model_smoke_test(report, args.model_cache)
        report["status"] = "PASS_STAGE_0"
    except Exception as exc:  # fail closed; preserve full report for audit
        report["status"] = "FAIL_STAGE_0"
        report["errors"].append(f"{type(exc).__name__}: {exc}")
    finally:
        report["elapsed_seconds"] = round(time.time() - started, 3)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": report.get("status"), "elapsed_seconds": report["elapsed_seconds"], "errors": report["errors"]}, ensure_ascii=False))
    return 0 if report.get("status") == "PASS_STAGE_0" else 2


if __name__ == "__main__":
    raise SystemExit(main())
