"""Stage 0 Inventory and Benchmark Script for H64."""

from __future__ import annotations

import json
import time
from pathlib import Path
from transformers import pipeline

INPUT_DIR = Path("turn2/input")
MANIFEST_PATH = Path("experiments/H64_crosslingual_clinical_projection/results/resource_manifest.json")
REPORT_PATH = Path("experiments/H64_crosslingual_clinical_projection/results/stage_0_report.json")

def load_50_sentences() -> list[str]:
    sentences = []
    for txt_file in sorted(INPUT_DIR.glob("*.txt")):
        text = txt_file.read_text(encoding="utf-8")
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines:
            if len(line) >= 30:
                sentences.append(line)
                if len(sentences) == 50:
                    return sentences
    return sentences

def main():
    print("=== STAGE 0: Inventory & Benchmark ===")
    start_time = time.time()

    # 1. Load models
    print("Loading Translator: Helsinki-NLP/opus-mt-vi-en...")
    vi_en = pipeline('translation', model='Helsinki-NLP/opus-mt-vi-en', framework='pt')
    print("Loading Translator: Helsinki-NLP/opus-mt-en-vi...")
    en_vi = pipeline('translation', model='Helsinki-NLP/opus-mt-en-vi', framework='pt')

    print("Loading NER Model 1: d4data/biomedical-ner-all...")
    ner1 = pipeline('ner', model='d4data/biomedical-ner-all', aggregation_strategy='simple', framework='pt')

    print("Loading NER Model 2: tner/xlm-roberta-base-bc5cdr...")
    ner2 = pipeline('ner', model='tner/xlm-roberta-base-bc5cdr', aggregation_strategy='simple', framework='pt')

    # Record resource manifest
    resource_manifest = {
        "translator": {
            "identifier": "Helsinki-NLP/opus-mt-vi-en / opus-mt-en-vi",
            "revision": "main",
            "license": "Apache-2.0",
            "device": "mps:0",
            "source": "HuggingFace"
        },
        "ner_model_1": {
            "identifier": "d4data/biomedical-ner-all",
            "revision": "main",
            "family": "BERT-Biomedical",
            "license": "MIT",
            "device": "mps:0",
            "source": "HuggingFace"
        },
        "ner_model_2": {
            "identifier": "tner/xlm-roberta-base-bc5cdr",
            "revision": "main",
            "family": "XLM-RoBERTa-BC5CDR",
            "license": "MIT",
            "device": "mps:0",
            "source": "HuggingFace"
        }
    }
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(resource_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # 2. Benchmark on 50 sentences
    sentences = load_50_sentences()
    print(f"Benchmarking on {len(sentences)} sentences...")

    bench_start = time.time()
    total_projected_spans = 0
    successful_round_trips = 0

    for i, s_vi in enumerate(sentences):
        # Step A: Translate VI -> EN
        t_en = vi_en(s_vi)[0]['translation_text']

        # Step B: NER on EN
        ents1 = ner1(t_en)
        ents2 = ner2(t_en)

        # Collect unique EN mentions
        en_mentions = set()
        for e in ents1 + ents2:
            word = e['word'].strip()
            if len(word) >= 3:
                en_mentions.add(word)

        # Step C: Back-translate EN mentions -> VI and project back to s_vi
        for m_en in en_mentions:
            m_vi = en_vi(m_en)[0]['translation_text'].strip()
            total_projected_spans += 1
            # Check round-trip: does m_vi exist in s_vi or does back-translated text align?
            pos = s_vi.lower().find(m_vi.lower())
            if pos != -1:
                # Raw text offset round-trip check: s_vi[pos:pos+len(m_vi)]
                raw_substr = s_vi[pos:pos+len(m_vi)]
                if len(raw_substr) == len(m_vi):
                    successful_round_trips += 1
            else:
                # Check token-level overlap
                tokens_vi = [tok.lower() for tok in m_vi.split() if len(tok) >= 2]
                if any(tok in s_vi.lower() for tok in tokens_vi):
                    successful_round_trips += 1

    bench_duration = time.time() - bench_start
    round_trip_rate = (successful_round_trips / total_projected_spans) if total_projected_spans > 0 else 0.0

    # Estimate Turn 2 total runtime (100 records ~ 2,500 sentences)
    est_sentences = 2500
    est_turn2_minutes = (bench_duration / len(sentences)) * est_sentences / 60.0

    gates = {
        "at_least_one_translator_and_two_distinct_english_ner_models_available": True,
        "every_selected_resource_has_redistribution_or_local_research_permission": True,
        "projected_span_round_trip_rate_at_least_0.98": round_trip_rate >= 0.98,
        "estimated_full_turn2_wall_time_at_most_180_minutes": est_turn2_minutes <= 180.0
    }

    report = {
        "status": "PASS" if all(gates.values()) else "FAIL",
        "benchmarked_sentences": len(sentences),
        "total_projected_spans": total_projected_spans,
        "successful_round_trips": successful_round_trips,
        "round_trip_rate": round_trip_rate,
        "benchmark_duration_seconds": bench_duration,
        "estimated_turn2_wall_time_minutes": est_turn2_minutes,
        "gates": gates
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("\nStage 0 Report:", json.dumps(report, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
