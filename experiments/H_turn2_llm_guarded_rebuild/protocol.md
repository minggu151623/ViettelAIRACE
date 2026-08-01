# H-T2 — Guarded LLM rebuild for Turn 2

## Status

Confirmatory protocol locked before running the Turn 2 LLM ablation. The
workspace is not a Git repository, so the protocol cannot be preregistered by
commit; this timestamped file is the local preregistration record.

## Baseline

- Artifact: `turn2/output.zip`
- External score: `16.6673`
- Text credit: `100 - WER = 19.6352`
- Assertion Jaccard: `24.9610`
- Candidate Jaccard: `8.2212`
- Score formula: `0.3 * text + 0.3 * assertion + 0.4 * candidate`

## Hypothesis

A local Qwen teacher can improve the Turn 2 artifact when it is used as a
bounded proposal and adjudication layer, rather than replacing the baseline.
The largest expected gains come from (a) recovering entities in empty and
abnormally sparse records, (b) making exact repeated passages consistent, and
(c) rejecting unsupported ICD/RxNorm candidates.

## Intervention

1. Keep raw LF positions and the existing assertion output by default.
2. Ask Qwen for structured entity proposals on every record, using exact raw
   substrings only.
3. Add proposals only in empty/sparse regions or when independently supported
   by a rule/dictionary detector; do not take a raw union.
4. Use exact repeated-text consensus to make identical passages deterministic.
5. For candidates, permit only identifiers retrieved from local ICD/RxNorm
   resources. Qwen may select or reject retrieved options but may not invent an
   identifier.
6. Reject anatomy-only, procedure-only, generic-category, and unsupported drug
   spans before serialization.

## Locked local evaluation

- 100/100 raw-LF schema and offset validation.
- Deterministic byte identity across two builds.
- No completely empty record when the input contains explicit structured
  diagnosis/symptom/test/drug fields.
- Manual error audit on records 1, 4, 14, 35, 56, 67, 75, 84, and 96.
- Report every addition, removal, retype, assertion change, and candidate
  change relative to the 16.6673 baseline.

## Abort criteria

- Any raw offset error.
- Unconstrained model-generated candidate ID.
- A broad union that increases entities by more than 50% without independent
  support.
- Recomputing all assertions without an isolated justification.

