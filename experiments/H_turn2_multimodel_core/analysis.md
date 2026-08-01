# H16 analysis — precision-gated three-model core

## Result

The three proposal banks were regenerated on the correct Turn 2 LF input:

- VietMed-NER: 3,689 usable proposals (plus ignored/noise labels)
- Bami v15 weighted: 3,728 proposals
- Bami v3: 2,938 proposals

Exact three-way span/type agreement outside the 1,540-entity guarded baseline
produced 345 rows. The sole drug row was the malformed fused string
`klonopinclonidine` and was rejected by the preregistered type gate. The final
intervention adds 344 entities:

- 47 diagnoses
- 280 symptoms
- 17 test names

The result contains 1,884 entities and touches 80 of 100 records. Fifty-four
new rows receive `isHistorical`, nineteen receive `isNegated`, and 18 of the 47
new diagnoses receive an ICD candidate through literal normalized alias lookup.
No fuzzy candidate lookup is permitted.

## Sanity checks

- 51/51 project tests pass.
- 100/100 outputs validate against raw LF text.
- Every offset round-trips to its exact raw substring.
- Two complete builds and ZIP packages are byte-identical.
- ZIP SHA-256: `24c12c819c5f6afd2dec4fb07d1f75c35b96c2f1a2229ef457d551952131dc2d`.

## Interpretation

The new proposals mostly recover repeated clinical mentions in explanatory and
history sections that the Qwen/rule baseline omitted. This is a materially
different recall mechanism from the prior empty-record repair. Exact agreement
across all three heterogeneous models is much cleaner than the 1,267 pair-only
rows, which remain quarantined.

The method is not guaranteed to improve the black-box score. The three models
still share some taxonomy errors: for example, they agree that one occurrence
of `bại não` is a symptom even though another baseline occurrence is a coded
diagnosis. Such conflicts are rare in the accepted set and remain an explicit
target for a later type-reconciliation experiment rather than an unregistered
edit to H16.

## Artifact

`turn2/output_v3_ensemble_core.zip`
