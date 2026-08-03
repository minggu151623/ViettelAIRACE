# Executor task H65 — corrected cross-lingual projection

## Read first

Read these files completely:

1. `experiments/H64_crosslingual_clinical_projection/audit.md`
2. `experiments/H65_crosslingual_projection_corrected_execution/protocol.yaml`
3. `experiments/H64_crosslingual_clinical_projection/protocol.yaml`
4. `literature/cross_lingual_clinical_projection.md`

The H64 commit is operationally safe but scientifically invalid. Do not merely
rerun `run_stage_0_benchmark.py` on a faster device.

## Deliverable

Return exactly one of:

- `FAIL` with the first failed frozen gate, evidence and no ZIP; or
- `PASS` with code, tests, reports, 100 validated JSON files, deterministic ZIP,
  SHA-256 and complete submission metrics if upload succeeds.

## Execution sequence

### 1. Sync and identity

Switch/pull `codex/core-rebuild-h57`. Verify baseline SHA-256 equals
`a9b9ae07997e57080ed8ce2ad9c390f4cd8c229e8eae8de447f6f47ae6ff4d0b`.
Never stage `external/`, caches, checkpoints, credentials or `scratch/`.

### 2. Use Colab CUDA as a compute worker

- Clone the exact protocol commit in Colab.
- Require `torch.cuda.is_available() == True`; otherwise record FAIL.
- Load all four models once and batch translation/NER.
- Save the real parameter device for every model. A string manually written in
  a manifest is not proof.
- Resolve every Hugging Face `main` to a commit SHA and record license and
  downloaded bytes.
- Persist cache/results to Drive or download them; never commit model weights.

### 3. Replace the invalid benchmark

Create a new module rather than editing history:

```text
airace/crosslingual_projection.py
experiments/H65_crosslingual_projection_corrected_execution/run.py
tests/test_crosslingual_projection.py
```

Use the deterministic 50-sentence PhoNER-dev sample in the protocol. Save its
IDs and SHA. Implement and report four separate quantities:

1. English two-model same-span/same-normalized-type consensus count.
2. Unique bidirectional Vietnamese alignment yield.
3. Exact raw offset fidelity among accepted projections.
4. Public-gold span/type precision, recall and F1.

Never call a token appearing somewhere in a line an exact round trip. Add unit
tests that would fail the old `any(tok in s_vi)` logic.

For ETA, call the production window builder on all 100 inputs and count its
actual windows. Report cold start separately from steady-state batched runtime.

### 4. Gate before proceeding

Write Stage-0 report, then evaluate the frozen gates mechanically. If any gate
fails, stop. Do not inspect Turn2 model output and do not create a ZIP.

Only after Stage 0 PASS, calibrate thresholds on official dev splits and open
official test once. If Stage 1 fails, stop without target inference.

### 5. Turn2 and packaging

Only after both source stages PASS, execute the inherited H64 conservative
fusion policy. Produce per-row provenance. Evaluate every target-blind gate
before packaging. A FAIL creates no ZIP.

For a PASS, validate all records, package twice and require identical bytes;
run the full test suite; record final SHA-256. Submit only that hash under the
user's existing authority and capture total score, WER, J_assertion and
J_candidates.

### 6. Report and Git

Update `findings.md`, `research-log.md` and `research-state.yaml` without
rewriting the H64 audit. Commit specific source/report files using:

```text
research(results): H65 — PASS|FAIL concise_reason
```

Push `codex/core-rebuild-h57` and report the commit plus artifact hash or first
failed gate.
