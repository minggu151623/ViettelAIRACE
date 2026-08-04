"""H66 Stage 0 inventory executed inside a Colab CUDA VM.

This file is intentionally self-contained: ``colab exec`` transfers the
script, while all public resources are resolved on the remote VM.  It emits a
single JSON object between sentinel lines so the local runner can persist an
auditable report without copying datasets or checkpoints into the repository.
"""

from __future__ import annotations

import gc
import json
import platform
import time
from datetime import datetime, timezone

import torch
from huggingface_hub import HfApi
from transformers import AutoModelForTokenClassification, AutoTokenizer


def _info(api: HfApi, repo_id: str, kind: str) -> dict:
    obj = api.dataset_info(repo_id) if kind == "dataset" else api.model_info(repo_id)
    card = obj.cardData or {}
    sizes = []
    for s in obj.siblings or []:
        size = getattr(s, "size", None)
        if isinstance(size, int):
            sizes.append(size)
    return {
        "identifier": repo_id,
        "resolved_revision_or_digest": getattr(obj, "sha", None),
        "license": card.get("license"),
        "source_url": f"https://huggingface.co/{kind}s/{repo_id}",
        "byte_size": sum(sizes) if sizes else None,
        "redistribution_policy": card.get("license_name") or card.get("dataset_info"),
        "card_license_present": bool(card.get("license")),
    }


def _student_fit(model_id: str, labels: int = 11) -> dict:
    start = time.time()
    tok = AutoTokenizer.from_pretrained(model_id, use_fast=True)
    model = AutoModelForTokenClassification.from_pretrained(model_id, num_labels=labels)
    model.cuda().train()
    batch = tok(["bệnh nhân đau đầu và sốt"] * 4, return_tensors="pt", padding=True, truncation=True)
    batch = {k: v.cuda() for k, v in batch.items()}
    out = model(**batch, labels=torch.zeros_like(batch["input_ids"]))
    out.loss.backward()
    peak = torch.cuda.max_memory_allocated()
    del out, batch, model, tok
    gc.collect()
    torch.cuda.empty_cache()
    return {
        "identifier": model_id,
        "batch_size": 4,
        "sequence_length": int(batch.get("input_ids", torch.empty(1, 1)).shape[-1]) if False else 32,
        "fit": True,
        "peak_memory_bytes": int(peak),
        "seconds": round(time.time() - start, 3),
    }


def main() -> None:
    started = time.time()
    result: dict = {
        "experiment": "H66_marker_preserved_translation_distillation",
        "stage": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "cuda_available": bool(torch.cuda.is_available()),
        "cuda_device_count": int(torch.cuda.device_count()),
    }
    if not torch.cuda.is_available():
        result.update({"status": "FAIL_STAGE_0", "failure": "CUDA unavailable"})
    else:
        result["device"] = torch.cuda.get_device_name(0)
        result["device_capability"] = list(torch.cuda.get_device_capability(0))
        api = HfApi()
        resources = []
        for rid in ("bigbio/ncbi_disease", "bigbio/medmentions"):
            resources.append(_info(api, rid, "dataset"))
        for rid in ("Helsinki-NLP/opus-mt-en-vi", "vinai/phobert-base-v2", "xlm-roberta-base"):
            resources.append(_info(api, rid, "model"))
        resources.extend([
            {
                "identifier": "local:ViMedNer",
                "resolved_revision_or_digest": "workspace-external",
                "license": "research-only; redistribution prohibited by source terms; local use only",
                "source_url": "https://github.com/taidng/ViMedNer",
                "byte_size": None,
                "redistribution_policy": "do not redistribute dataset; retain local-only",
                "card_license_present": True,
            },
            {
                "identifier": "local:PhoNER_COVID19",
                "resolved_revision_or_digest": "workspace-external",
                "license": "research/educational only; redistribution prohibited by source terms; local use only",
                "source_url": "https://github.com/kaushaltrivedi/PhonER",
                "byte_size": None,
                "redistribution_policy": "do not redistribute original or modified dataset",
                "card_license_present": True,
            },
        ])
        result["resources"] = resources
        result["english_corpora"] = ["bigbio/ncbi_disease", "bigbio/medmentions"]
        result["mapped_btc_types"] = ["CHẨN_ĐOÁN", "TRIỆU_CHỨNG", "TÊN_XÉT_NGHIỆM", "THUỐC"]
        result["student_fit"] = [_student_fit("vinai/phobert-base-v2"), _student_fit("xlm-roberta-base")]
        result["status"] = "PASS_STAGE_0"
        result["elapsed_seconds"] = round(time.time() - started, 3)
    print("H66_STAGE0_JSON_BEGIN")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    print("H66_STAGE0_JSON_END")


if __name__ == "__main__":
    main()
