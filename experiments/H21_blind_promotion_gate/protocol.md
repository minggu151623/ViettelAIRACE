# H21 — Blind validation and safe promotion gate

## Status

Preregistered before calibration record selection, annotation, evaluator runs,
or challenger comparison. The externally scored H20 artifact remains frozen.

## Problem

The leaderboard is a scarce hidden test and cannot serve as the inner-loop
objective. The existing nine-record `manual_validation.jsonl` exactly matches a
legacy generated output and is circular. H21 must create a separate evaluation
track whose record selection does not inspect H20 or any model proposal.

## Hypothesis

A length- and structure-stratified, prediction-blind review set plus paired
bootstrap uncertainty will reject unstable challengers more reliably than
leaderboard-driven micro-variants. A selective challenger that fails the gate
must fall back to H20 rather than replacing the frozen baseline.

## Frozen design

- Corpus: `turn2/input`, exactly 100 LF UTF-8 records.
- Selection inputs: raw text length and deterministic structural counts only
  (lines, sections, bullets and table-like rows). No predictions or outputs.
- Queue size: 18 records, selected across six structural strata.
- Development split: 12 records used for diagnosis and calibration.
- Holdout split: 6 records; hidden from routine evaluation until a challenger
  and its decision thresholds are frozen.
- Annotation begins from an empty prediction directory.
- Every occurrence is labeled independently with exact `[start,end)` offsets.
- Candidates remain empty unless independently verified from the frozen
  ontology resources.
- Random operations use seed `298409`.

The selector records the SHA-256 of every chosen raw file and the full corpus
fingerprint. Any input change invalidates the manifest.

## Primary measures

For each record, compare H20 and challenger against reviewed labels using the
same reconstructed competition metric. Report paired deltas for:

- final score;
- text score;
- assertion Jaccard;
- weighted candidate Jaccard;
- strict span/type precision, recall and F1.

Uncertainty is estimated with 10,000 paired record-level bootstrap resamples.

## Promotion gate

A challenger is `PROMOTE` only when all conditions hold on the untouched
holdout:

1. mean reconstructed final-score delta is at least `+0.03` (+3 percentage
   points);
2. the 95% paired-bootstrap lower bound for final-score delta is greater than
   zero;
3. strict span/type F1 does not decrease;
4. no component mean decreases by more than `0.01` (1 percentage point);
5. at least half of holdout records are non-regressing on final score;
6. both baseline and challenger pass schema/offset validation;
7. results are deterministic under a repeated evaluator run.

`REJECT` means keep H20. `INSUFFICIENT_EVIDENCE` means continue offline work;
it is not permission to spend a leaderboard submission.

## Selective fallback rule

H20 is the default output. A later learned selector may replace an entity or
record only from frozen, model-independent features calibrated on development
data. Holdout labels and leaderboard results may evaluate that selector but may
not alter its thresholds. No manual record-id allowlist is permitted.

## Expected failure modes

- The small holdout may have wide confidence intervals.
- Human policy may differ from organizer policy.
- Correlated Bami checkpoints can create false consensus.
- Candidate labels are expensive and may be too sparse for a decisive gate.

These limitations must be reported explicitly; no internal result is a
guarantee of hidden leaderboard improvement.

## Planned artifacts

```text
experiments/H21_blind_promotion_gate/
├── protocol.md
├── calibration_manifest.json
├── no_predictions/
├── annotations/
├── reports/
└── analysis.md
```

No competition submission is performed by Codex.

