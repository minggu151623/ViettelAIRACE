# H17 — Independent learned-pair proposals with Qwen adjudication

## Baseline

- Artifact: `turn2/output_v3_ensemble_core.zip`
- External score: 21.4739
- WER: 74.5424
- J_assertion: 30.2734
- J_candidates: 11.8865

H16 improved every metric over 19.0709. Its exact three-model additions account
for a +2.4030 point gain, including +1.1690 from text credit, +0.9562 from
assertions, and +0.2778 from candidates.

## Hypothesis

Some correct entities are recognized by VietMed-NER and exactly one Bami model
but missed by the other Bami checkpoint. Requiring an independent VietMed+Bami
exact span/type pair, deterministic type-specific confidence floors, and two
stable KEEP votes from Qwen should recover a smaller recall layer while
excluding the correlated Bami-v15+Bami-v3-only proposal mass.

## Frozen eligibility policy

- Proposal is absent from the 1,884-entity H16 baseline.
- Exact text, `[start,end)`, and type agreement includes `vietmed_ner` plus
  `bami_v15` or `bami_v3`.
- Proposals already supported by all three models are excluded as H16 rows.
- Eligible types: diagnosis, symptom, and test name only.
- Drug and result proposals are excluded from H17.
- Confidence floors:
  - VietMed >= 0.85;
  - Bami diagnosis >= 0.58;
  - Bami symptom >= 0.60;
  - Bami test name >= 0.38.
- Raw substring and single-line validation must pass.
- Generic headings and non-clinical fragments are rejected deterministically.

## Qwen adjudication

- Qwen receives only the proposed mention, fixed type, local context, source
  confidences, and section/line context.
- It may KEEP or DROP; it cannot alter span, type, assertions, or candidates.
- Two runs use temperature zero and different fixed seeds.
- Accept only rows receiving KEEP in both runs, each with confidence >= 0.80.
- The model must return a complete schema-constrained decision list. Missing or
  unstable decisions are DROP.

## Output policy

- Preserve every H16 entity and field.
- Infer assertions for accepted additions with the existing scope engine.
- Add ICD only through exact normalized alias lookup; never fuzzy containment.
- No RxNorm change.

## Acceptance criteria

1. At least 20 stable additions, otherwise H17 is not worth a leaderboard test.
2. A stratified local context audit contains no more than 10% obvious false
   positives or wrong types.
3. 100/100 records validate; all tests pass.
4. Two builds and ZIPs are byte-identical.
5. Full decision provenance and rejection reasons are written to JSON.

No submission is performed automatically.
