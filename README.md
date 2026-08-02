# Viettel AI Race medical workflow

> **Current frozen Turn 2 baseline: 29.8409.** Start with
> [`BASELINE_29_8409.md`](BASELINE_29_8409.md) for the exact artifact checksum,
> external metrics, architecture and collaboration rules. Do not overwrite that
> baseline with an unscored experiment.

Offline workflow for the medical concept extraction task.

## V6 structural + RxNorm-only candidate policy

The best current offline artifact is `output_v6_structural_btc.zip`.

V6 keeps V5's grounded Qwen spans, then applies section-aware cleanup for
generic headings, surgical procedures, nested wrong-type spans, attribute-only
values, and pathological clinical findings. It also recognizes coagulation
factor concentrates as medication products.

Most importantly, V6 no longer emits ICD-10 IDs for diagnoses. The organiser's
PDF demonstrates RxNorm candidates for medication but does not identify ICD-10
as the diagnosis candidate ontology. Submitting ICD IDs in that field was
therefore an unsupported assumption and created 124 likely false candidate
sets. Drug RxCUIs are retained.

```bash
/opt/anaconda3/bin/python -m airace v6-rebuild \
  --source output_v5_precision_btc \
  --output output_v6_structural \
  --report reports/v6_structural.json \
  --structural-cleanup

/opt/anaconda3/bin/python -m airace format-btc \
  --input input \
  --source output_v6_structural \
  --output output_v6_structural_btc

/opt/anaconda3/bin/python -m airace package \
  --input input \
  --output output_v6_structural_btc \
  --zip output_v6_structural_btc.zip
```

Validation status: 19 tests pass, all 100 output files validate, two repeated
runs are byte-identical, and the nine-record reviewed proxy reaches 40/40
strict span/type matches. That proxy was used to design some general cleanup
rules and is therefore optimistic; leaderboard feedback remains the only
independent evaluation.

## Leaderboard evidence

The direct Qwen3 hybrid improved the public score from `0.3690` to `1.3060`.
Its assertion score increased from `0.9248` to `2.5774`, and candidate score
from `0.1933` to `1.3028`, but WER moved from `99.9525` to `99.9611`. This is
evidence that span boundaries and entity types, not only ICD/RxNorm lookup, are
the main bottleneck.

V3 therefore does not ask Qwen to be the final detector. It uses:

1. Qwen3 for broad proposals.
2. Deterministic medication/lab rules for high-precision proposals.
3. BamiBERT-ViMedNER as a Vietnamese biomedical span teacher.
4. Consensus labels, with manually reviewed records held out.
5. A sliding-window token classifier fine-tuned for the six competition types.
6. Local assertion and candidate resolution after span/type prediction.

Create the consensus data while excluding the reviewed validation records:

```bash
python -m airace prepare-silver \
  --input input \
  --qwen output_qwen3_hybrid \
  --teacher cbc-528a/BamiBERT-ViMedNER \
  --output labels/silver_consensus.jsonl \
  --holdout-labels labels/manual_validation.jsonl \
  --consensus-output output_v3_consensus \
  --report reports/silver_consensus.json

python -m airace train \
  --labels labels/silver_consensus.jsonl \
  --validation-labels labels/manual_validation.jsonl \
  --base-model cbc-528a/BamiBERT-ViMedNER \
  --output models/bami-airace-v3

python -m airace infer \
  --input input \
  --output output_v3_token \
  --model-checkpoint models/bami-airace-v3 \
  --report reports/v3_token.json
```

Unlike the V1 trainer, V3 uses 256-token windows with 64-token overlap and
processes the entire document. It saves the checkpoint with the best strict
span/type F1 on reviewed records and stops early when that score no longer
improves.

Reviewing labels now uses an editable table with automatic exact-offset
validation:

```bash
python -m airace annotate \
  --input input \
  --pred output_v3_consensus \
  --out labels/annotations.jsonl
```

Do not submit a V3 ZIP only because training completed. First compare its strict
span/type metrics on `labels/manual_validation.jsonl`; the reviewed set is the
submission gate.

For the Turn-2 prediction-blind repeated-passage study, use the separate H41
workflow. It never loads a model output and keeps assertions occurrence-specific:

```bash
python -m airace passage-blind-prepare
python -m airace passage-queue-audit
python -m airace passage-annotate --reviewer reviewer_1 \
  --out experiments/H41_repeated_passage_blind_annotation/labels/reviewer_1.jsonl
```

See `experiments/H41_repeated_passage_blind_annotation/README.md` for the
independent two-reviewer protocol. No H41 submission artifact is created before
the locked holdout gate passes.

## Legacy V2 baselines

The repository also contains the older rule profiles:

```bash
python -m airace prepare-resources --download-rxnorm

python -m airace infer --input input --output output_v2_precision \
  --profile precision --report reports/v2_precision.json
python -m airace validate --input input --output output_v2_precision
python -m airace package --input input --output output_v2_precision \
  --zip output_v2_precision.zip

python -m airace infer --input input --output output_v2_recall \
  --profile recall --report reports/v2_recall.json
python -m airace package --input input --output output_v2_recall \
  --zip output_v2_recall.zip

# Conservative candidate ablation for controlled submission testing
python -m airace infer --input input --output output_v2_baseline_strength \
  --profile baseline_strength --report reports/v2_baseline_strength.json

python -m airace infer --input input --output output_v2_section_only \
  --profile section_only --report reports/v2_section_only.json
```

The original baseline remains available in `output/`; the clean package is
`output_baseline_clean.zip`. `baseline_strength` keeps the baseline spans and
assertions, adding candidates only to dosage-bearing drug mentions with a
matched product RxCUI. Submit this after the clean baseline as an isolated
candidate experiment. `section_only` keeps the baseline candidate strategy and
adds only structured-section symptom/diagnosis spans; it is the final
high-recall experiment for a limited submission budget. The recall profile adds
both those spans and lower-confidence RxNorm drug entities and is intended for a
controlled leaderboard comparison.
Both profiles are deterministic and use local regexes, dictionaries,
section-aware assertion rules, and an offline RxNorm Current Prescribable Content
catalog. Candidate selection emits top-1 only. PhoBERT is intentionally not used
until a fine-tuned checkpoint is available.

Compare the two profiles with the original baseline:

```bash
python -m airace audit --baseline output \
  --precision output_v2_precision --recall output_v2_recall \
  --report reports/v2_audit.json
```

## Current high-recall candidate

The current candidate workflow uses a locally hosted Qwen3 8B model through
Ollama. It proposes unique `(text, type)` concepts; the Python pipeline then
grounds every occurrence against the raw input, recomputes assertions locally,
resolves local ICD/RxNorm candidates, and validates the result.

```bash
python -m airace llm-infer \
  --input input \
  --output output_qwen3_hybrid \
  --report reports/qwen3_hybrid.json \
  --model qwen3:8b

python -m airace validate --input input --output output_qwen3_hybrid
python -m airace package --input input \
  --output output_qwen3_hybrid --zip output_qwen3_hybrid.zip
```

`llm-infer` resumes existing JSON files by default. The model must be installed
in Ollama (`ollama list` should show `qwen3:8b`). The current artifact is
`output_qwen3_hybrid.zip`; it contains exactly 100 files under `output/` and
passed the local validator. It scored `1.3060`, so it is now a proposal source,
not the final architecture.

## Controlled rollback after V3

The consensus experiment `output_v3_consensus_full.zip` changed 415 exact
span/type records relative to Qwen and removed eight candidate-bearing
entities. Its public score fell to `1.2726`. The conservative recovery command
keeps Qwen's `text`, `type`, `position`, and `candidates` fields, and refreshes
only local assertion scope:

```bash
python -m airace assertion-preserve \
  --input input \
  --source output_qwen3_hybrid \
  --output output_v4_assertion_preserve \
  --report reports/v4_assertion_preserve.json
python -m airace validate --input input --output output_v4_assertion_preserve
python -m airace package --input input \
  --output output_v4_assertion_preserve \
  --zip output_v4_assertion_preserve.zip
```

This is an isolated candidate for review, not an automatic submission. It
contains 100 JSON files, 167 drugs, 411 diagnoses, and 226 assertion changes;
all offsets and candidate lists are preserved from the scored Qwen artifact.

## V5 ICD and precision variants

V5 adds an offline ICD-10-CM FY2026 code index and a two-pass Ollama alias
audit. The full model map is retained for review, but only a small reviewed
high-precision alias set is activated in the ICD variant:

```bash
python -m airace prepare-icd-aliases \
  --source output_v4_assertion_preserve \
  --output airace/resources/icd10cm_aliases_v5.json
python -m airace v5-reconcile \
  --input input \
  --source output_v4_assertion_preserve \
  --aliases airace/resources/icd10cm_aliases_v5.json \
  --output output_v5_icd_consensus \
  --report reports/v5_icd_consensus.json
```

Because the reviewed holdout has mostly empty diagnosis candidates, a safer
ablation is also produced with `--no-icd`; it keeps every Qwen candidate list
and removes only ten unmistakable noise entities:

```bash
python -m airace v5-reconcile \
  --input input \
  --source output_v4_assertion_preserve \
  --aliases airace/resources/icd10cm_aliases_v5.json \
  --output output_v5_precision \
  --report reports/v5_precision.json \
  --no-icd
```

Neither V5 artifact is submitted automatically. They are deliberately
separated so the next blind submission can choose between candidate recall
and candidate precision instead of changing both at once.
