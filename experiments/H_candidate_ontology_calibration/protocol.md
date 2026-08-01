# H2 — Candidate ontology calibration

## Status

Supported by the V5→V6 black-box ablation. The bare-generic RxNorm resolver
defect is repaired and regression-tested; a controlled candidate-only
comparison remains pending.

## Hypothesis

Candidates are scored by weighted Jaccard, so unsupported codes are costly.
When ontology evidence is unavailable, an empty candidate list is safer than a
hallucinated ICD code. RxNorm candidates should be retained only for drug
mentions with a defensible ingredient/strength/form match.

## Evidence already observed

The V5→V6 external result changed from candidate score 1.3028 to 2.0991 while
WER and assertion values stayed fixed. The resulting total delta is
`0.4 * (2.0991 - 1.3028) = 0.31852`, exactly matching the reported score gain.

## Procedure

Compare:

- V6 structural policy;
- RxNorm-only policy;
- empty-candidate ablation.

Keep all non-candidate fields byte-equivalent where possible. Report both local
candidate coverage and the external leaderboard result, without treating the
latter as a causal proof beyond this controlled comparison.

Before any comparison, preserve the following conformance rule: a bare generic
drug mention uses its exact RxNorm alias (`IN`/`PIN`/`MIN`) rather than the
first ID from the broad product index. Product selection is allowed only when
the mention explicitly supports a strength, form, route, or brand.

## Decision rule

Retain the policy with the highest external candidate score only if WER and
assertion metrics do not regress materially. If no external test remains, keep
V6 as the default and mark the comparison unresolved.
