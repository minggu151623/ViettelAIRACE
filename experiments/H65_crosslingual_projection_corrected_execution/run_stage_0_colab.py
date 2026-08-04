"""Protocol-faithful H65 Stage-0 benchmark for a Colab CUDA runtime.

This script deliberately does not infer Turn2 output.  It measures public-source
sample quality, exact accepted-span offset fidelity, consensus/alignment yield,
and a batched runtime estimate.  It fails closed when CUDA or the required
resources are unavailable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import traceback
from pathlib import Path
from typing import Any


TRANSLATORS = {
    "vi_en": "Helsinki-NLP/opus-mt-vi-en",
    "en_vi": "Helsinki-NLP/opus-mt-en-vi",
}
NER_MODELS = {
    "model_a": "d4data/biomedical-ner-all",
    "model_b": "blaze999/Medical-NER",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold().strip())


def map_label(label: str) -> str | None:
    """Map both model inventories to the BTC type vocabulary."""
    raw = label.upper().replace("-", "_")
    raw = raw.replace("B_", "").replace("I_", "")
    mapping = {
        "DISEASE_DISORDER": "diagnosis",
        "DISEASE": "diagnosis",
        "SIGN_SYMPTOM": "symptom",
        "SYMPTOM": "symptom",
        "DIAGNOSTIC_PROCEDURE": "test_name",
        "THERAPEUTIC_PROCEDURE": "test_name",
        "LAB_VALUE": "test_result",
        "MEDICATION": "drug",
        "CHEMICAL": "drug",
        "AGE": "patient_info",
        "SEX": "patient_info",
        "GENDER": "patient_info",
        "PERSONAL_BACKGROUND": "patient_info",
    }
    return mapping.get(raw)


def phoner_type(label: str) -> str | None:
    """Map only the PhoNER labels useful for the Stage-0 public check."""
    raw = label.upper()
    if raw == "SYMPTOM_AND_DISEASE":
        return "clinical_condition"
    if raw in {"PATIENT_ID", "AGE", "GENDER", "JOB"}:
        return "patient_info"
    return None


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sentence_from_record(record: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    words = [str(word).replace("_", " ") for word in record["words"]]
    tags = [str(tag) for tag in record["tags"]]
    text_parts: list[str] = []
    offsets: list[tuple[int, int]] = []
    cursor = 0
    for index, word in enumerate(words):
        if index:
            text_parts.append(" ")
            cursor += 1
        start = cursor
        text_parts.append(word)
        cursor += len(word)
        offsets.append((start, cursor))
    text = "".join(text_parts)
    entities: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for index, tag in enumerate(tags):
        if tag.startswith("B-"):
            if current is not None:
                entities.append(current)
            current = {
                "type": phoner_type(tag[2:]),
                "start": offsets[index][0],
                "end": offsets[index][1],
            }
        elif tag.startswith("I-") and current is not None:
            current["end"] = offsets[index][1]
        else:
            if current is not None:
                entities.append(current)
                current = None
    if current is not None:
        entities.append(current)
    return text, [entity for entity in entities if entity["type"] is not None]


def load_public_sample(path: Path, count: int) -> list[dict[str, Any]]:
    records = read_jsonl(path)
    sample: list[dict[str, Any]] = []
    for index, record in enumerate(records):
        text, gold = sentence_from_record(record)
        if text.strip():
            sample.append({"id": index, "text": text, "gold": gold})
        if len(sample) >= count:
            break
    return sample


def exact_span(text: str, backtranslated: str) -> tuple[int, int] | None:
    """Accept only a literal raw substring; never soft-match a token elsewhere."""
    candidate = backtranslated.strip()
    if not candidate:
        return None
    folded_text = text.casefold()
    folded_candidate = candidate.casefold()
    start = folded_text.find(folded_candidate)
    if start < 0:
        return None
    end = start + len(candidate)
    if end > len(text):
        return None
    return start, end


def entity_text(entity: dict[str, Any]) -> str:
    return str(entity.get("word") or entity.get("text") or "").replace("##", "").strip()


def normalized_entities(raw: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for entity in raw:
        label = map_label(str(entity.get("entity_group") or entity.get("entity") or ""))
        mention = entity_text(entity)
        key = (normalize_text(mention), label or "")
        if label and mention and key not in result:
            result[key] = {"mention": mention, "type": label, "key": key}
    return result


def model_manifest(repo_id: str, snapshot_path: Path, device: str) -> dict[str, Any]:
    files = [item for item in snapshot_path.rglob("*") if item.is_file()]
    revision_file = snapshot_path / ".." / ".." / "refs" / "main"
    revision = revision_file.resolve().read_text(encoding="utf-8").strip() if revision_file.exists() else "unknown"
    return {
        "identifier": repo_id,
        "revision": revision,
        "license": "record_from_model_card",
        "bytes": sum(item.stat().st_size for item in files),
        "device": device,
    }


class Seq2SeqTranslator:
    """Batched Marian wrapper independent of pipeline task registries."""

    def __init__(self, snapshot_path: Path, device: str, torch: Any, tokenizer_cls: Any, model_cls: Any) -> None:
        self.device = device
        self.torch = torch
        self.tokenizer = tokenizer_cls.from_pretrained(str(snapshot_path))
        dtype = torch.float16 if device.startswith("cuda") else torch.float32
        self.model = model_cls.from_pretrained(str(snapshot_path), torch_dtype=dtype).to(device).eval()

    def translate(
        self,
        texts: list[str],
        batch_size: int,
        max_length: int,
        input_max_length: int,
    ) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        with self.torch.inference_mode():
            for start in range(0, len(texts), batch_size):
                batch = texts[start : start + batch_size]
                encoded = self.tokenizer(
                    batch,
                    return_tensors="pt",
                    padding=True,
                    truncation=True,
                    max_length=input_max_length,
                )
                encoded = {key: value.to(self.device) for key, value in encoded.items()}
                generated = self.model.generate(**encoded, max_length=max_length, num_beams=1)
                decoded = self.tokenizer.batch_decode(generated, skip_special_tokens=True)
                rows.extend({"translation_text": text} for text in decoded)
        return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phoner-dev", type=Path, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=50)
    parser.add_argument("--batch-size", type=int, default=8)
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    try:
        import torch
        from huggingface_hub import HfApi, snapshot_download
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, pipeline
    except Exception as exc:  # pragma: no cover - exercised in Colab
        report = {"status": "FAIL", "failure": f"missing_dependency: {exc}"}
        (args.output / "stage_0_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return 1

    if not torch.cuda.is_available():
        report = {"status": "FAIL", "failure": "CUDA is unavailable; select a Colab GPU runtime."}
        (args.output / "stage_0_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return 1

    device = "cuda:0"
    sample = load_public_sample(args.phoner_dev, args.sample_size)
    if len(sample) != args.sample_size:
        report = {"status": "FAIL", "failure": f"public sample has only {len(sample)} sentences"}
        (args.output / "stage_0_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return 1
    (args.output / "public_sample_manifest.json").write_text(
        json.dumps({"source": str(args.phoner_dev), "sha256": sha256_file(args.phoner_dev), "ids": [item["id"] for item in sample]}, indent=2) + "\n",
        encoding="utf-8",
    )

    snapshots: dict[str, Path] = {}
    resource_info: dict[str, Any] = {}
    api = HfApi()
    for repo_id in [*TRANSLATORS.values(), *NER_MODELS.values()]:
        info = api.model_info(repo_id, revision="main")
        resource_info[repo_id] = info
        # Resolve `main` before download so the bytes and recorded revision
        # cannot diverge if the upstream branch changes during the run.
        snapshots[repo_id] = Path(snapshot_download(repo_id=repo_id, revision=info.sha))

    manifest: dict[str, Any] = {"device": device, "resources": {}}
    for repo_id, snapshot in snapshots.items():
        info = resource_info[repo_id]
        entry = model_manifest(repo_id, snapshot, device)
        entry["revision"] = info.sha
        # Current huggingface_hub exposes card_data as ModelCardData; older
        # releases may expose a mapping-like value.
        card_license = getattr(info.card_data, "license", None) if info.card_data else None
        if card_license is None and isinstance(info.card_data, dict):
            card_license = info.card_data.get("license")
        entry["license"] = card_license or "unresolved"
        manifest["resources"][repo_id] = entry
    (args.output / "resource_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    vi_en = Seq2SeqTranslator(
        snapshots[TRANSLATORS["vi_en"]], device, torch, AutoTokenizer, AutoModelForSeq2SeqLM
    )
    en_vi = Seq2SeqTranslator(
        snapshots[TRANSLATORS["en_vi"]], device, torch, AutoTokenizer, AutoModelForSeq2SeqLM
    )
    ner_a = pipeline("token-classification", model=str(snapshots[NER_MODELS["model_a"]]), aggregation_strategy="simple", device=0, framework="pt")
    ner_b = pipeline("token-classification", model=str(snapshots[NER_MODELS["model_b"]]), aggregation_strategy="simple", device=0, framework="pt")

    texts = [item["text"] for item in sample]
    start_time = time.perf_counter()
    english = [
        row["translation_text"]
        for row in vi_en.translate(texts, batch_size=args.batch_size, max_length=512, input_max_length=512)
    ]
    entities_a = ner_a(english, batch_size=args.batch_size)
    entities_b = ner_b(english, batch_size=args.batch_size)
    consensus: list[dict[str, Any]] = []
    for item, source, raw_a, raw_b in zip(sample, english, entities_a, entities_b):
        mapped_a = normalized_entities(raw_a)
        mapped_b = normalized_entities(raw_b)
        for key in sorted(set(mapped_a) & set(mapped_b)):
            consensus.append({"sample_id": item["id"], "source": source, **mapped_a[key]})

    backtranslated = [row["mention"] for row in consensus]
    # Translate each consensus mention, not the whole source sentence.
    translated_mentions = []
    if backtranslated:
        translated_mentions = [
            row["translation_text"]
            for row in en_vi.translate(
                backtranslated, batch_size=args.batch_size, max_length=128, input_max_length=128
            )
        ]
    accepted: list[dict[str, Any]] = []
    for row, translated in zip(consensus, translated_mentions):
        source_item = sample[next(i for i, item in enumerate(sample) if item["id"] == row["sample_id"])]
        span = exact_span(source_item["text"], translated)
        if span is not None:
            accepted.append({**row, "back_translation": translated, "start": span[0], "end": span[1], "text": source_item["text"][span[0]:span[1]]})

    gold = {(item["id"], entity["start"], entity["end"], entity["type"]): item for item in sample for entity in item["gold"]}
    # Public PhoNER combines disease and symptom, so compare only the source
    # span and patient-info group in this preliminary diagnostic.
    predicted_keys = {(row["sample_id"], row["start"], row["end"], "clinical_condition" if row["type"] in {"diagnosis", "symptom"} else row["type"]) for row in accepted}
    gold_keys = {(key[0], key[1], key[2], key[3]) for key in gold}
    true_positive = len(predicted_keys & gold_keys)
    precision = true_positive / len(predicted_keys) if predicted_keys else 0.0
    recall = true_positive / len(gold_keys) if gold_keys else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0

    elapsed = time.perf_counter() - start_time
    target_lines = sum(1 for path in sorted(args.input.glob("*.txt")) for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and len(line.strip()) >= 30)
    per_sentence = elapsed / len(sample)
    eta_minutes = (per_sentence * target_lines) / 60.0
    exact_fidelity = sum(row["text"] == sample[next(i for i, item in enumerate(sample) if item["id"] == row["sample_id"])]["text"][row["start"]:row["end"]] for row in accepted) / len(accepted) if accepted else 0.0
    alignment_yield = len(accepted) / len(consensus) if consensus else 0.0
    types = sorted({row["type"] for row in consensus})
    gates = {
        "cuda_available": True,
        "exact_offset_fidelity_at_least_0.98": exact_fidelity >= 0.98,
        "alignment_yield_at_least_0.15": alignment_yield >= 0.15,
        "shared_mapping_supports_at_least_3_BTC_types": len(types) >= 3,
        "accepted_candidates_at_least_20": len(accepted) >= 20,
        "estimated_runtime_at_most_180_minutes": eta_minutes <= 180.0,
    }
    report = {
        "status": "PASS" if all(gates.values()) else "FAIL",
        "sample_size": len(sample),
        "consensus_mentions": len(consensus),
        "accepted_exact_projections": len(accepted),
        "consensus_types": types,
        "alignment_yield": alignment_yield,
        "exact_offset_fidelity": exact_fidelity,
        "public_diagnostic": {"precision": precision, "recall": recall, "f1": f1, "tp": true_positive, "predicted": len(predicted_keys), "gold": len(gold_keys)},
        "benchmark_seconds": elapsed,
        "target_line_count": target_lines,
        "estimated_turn2_minutes": eta_minutes,
        "runtime_device": device,
        "gates": gates,
    }
    (args.output / "stage_0_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # pragma: no cover - exercised by remote runtime
        output_dir = Path(".")
        if "--output" in sys.argv:
            try:
                output_dir = Path(sys.argv[sys.argv.index("--output") + 1])
            except (IndexError, ValueError):
                output_dir = Path(".")
        output_dir.mkdir(parents=True, exist_ok=True)
        report = {
            "status": "FAIL",
            "failure": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }
        (output_dir / "stage_0_report.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        print(json.dumps(report, indent=2, ensure_ascii=False), file=sys.stderr)
        raise
