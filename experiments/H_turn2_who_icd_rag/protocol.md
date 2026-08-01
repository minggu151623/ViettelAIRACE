# H18 — WHO ICD-10 candidate-only ontology reconstruction

## Baseline

- Artifact: `turn2/output_v4_pair_qwen.zip`
- External score: 21.8139
- WER: 74.0072
- J_assertion: 30.7601
- J_candidates: 11.9700

H17 added only +0.3400. Recall layers remain positive but are saturating.
Candidate Jaccard is the lowest component and carries the largest score weight.

## Mechanistic hypothesis

The organizer states that diagnosis coding uses a Vietnamese ICD-10 edition,
while the pipeline was built around a mixture of WHO ICD-10 and US ICD-10-CM.
Of 388 current diagnosis-code uses, 39 use a code absent from WHO ICD-10 2019
even though its three-character WHO category exists. In addition, 126 diagnosis
entities have empty candidates. Reconstructing candidates against one frozen
WHO ontology, with retrieval-augmented Qwen adjudication and parent/specific
candidate support, should improve J_candidates without changing WER or
assertions.

## Frozen fields

Every `text`, `type`, `position`, and `assertions` field from H17 is immutable.
Drug candidates are also immutable in H18. Only candidates of `CHẨN_ĐOÁN` may
change.

## Candidate construction

1. Parse the official local WHO ICD-10 2019 systematic code file using field 6
   as the canonical dotted code and field 8 as its title.
2. Preserve a current code that exists exactly in WHO ICD-10.
3. For a current ICD-10-CM-only code, propose its valid three-character WHO
   category and remove the non-WHO code.
4. For every unique diagnosis mention, Qwen proposes zero to two WHO ICD-10
   codes from context. Every proposed code must exist in the frozen catalog.
5. Candidate pool may also include the valid three-character parent of a
   current/proposed specific code, reflecting the organizer example that lists
   both parent and specific candidates.
6. A second schema-constrained Qwen pass sees the exact WHO English titles and
   may keep or reject each pooled code. It cannot invent codes.
7. Generated additions require proposer confidence >= 0.90 and reviewer
   confidence >= 0.90. Deterministic CM-to-WHO parent repair requires reviewer
   confidence >= 0.85. Existing exact WHO codes remain preserved.
8. Emit at most two codes, preferring a valid parent plus the most specific
   supported child. Abstain for noise, procedures, findings, or ambiguity.

## Acceptance criteria

- At least 30 diagnosis entity uses gain or repair a candidate.
- No code absent from WHO ICD-10 2019 remains.
- Manual stratified audit finds <=10% clearly semantically wrong additions.
- Non-diagnosis candidate fields and all frozen fields are byte-equivalent.
- 100/100 records validate; all tests pass; two ZIP builds are byte-identical.

This is a candidate-only external test. No submission is performed by Codex.
