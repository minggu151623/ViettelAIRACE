# H16 — Turn 2 precision-gated multi-model core

## Status

Confirmatory protocol locked before proposal generation and merging. The
workspace root is not a Git repository, so temporal locking is represented by
this file and the research log rather than a protocol commit.

## Baseline

- Artifact: `turn2/output_v2_llm_guarded.zip`
- External score: 19.0709
- WER: 78.4389
- J_assertion: 27.0860
- J_candidates: 11.1919

## Hypothesis

The rule/Qwen baseline misses a substantial number of organizer entities.
Independent token classifiers have complementary recall, but their raw union
is too noisy. Exact span/type agreement between heterogeneous models, combined
with baseline-overlap and type-specific gates, should recover missing entities
without the false-positive explosion observed in earlier ensemble attempts.

## Frozen proposal sources

1. VietMed-NER (`leduckhai/VietMed-NER`)
2. Bami AIRace v15 weighted
3. Bami AIRace v3
4. Existing guarded Qwen/rule output only as baseline evidence, not a vote that
   can manufacture a learned-model consensus.

## Primary intervention

- Preserve every baseline entity and its fields unless an exact duplicate is
  consolidated.
- Add an unseen span only when at least two independent learned models agree on
  exact `[start,end)`, text, and type.
- Use stricter, type-specific policy:
  - diagnosis/symptom/test/patient: two-model exact agreement is eligible;
  - drug: require all three models or independent drug lexicon support;
  - result: require all three models or deterministic numeric-lab structure.
- Reject generic headings, malformed boundaries, cross-line spans, isolated
  punctuation/numbers, and candidates unsupported by the existing resolver.
- Infer assertions conservatively from the existing assertion engine.
- For new diagnosis/drug entities, emit candidates only when the deterministic
  resolver has exact/high-confidence support; otherwise emit an empty list.

## Confirmatory prediction

- The merged candidate contains materially more high-consensus entities than
  the 1,540-entity baseline while retaining zero schema/offset failures.
- Added spans have substantially higher cross-model support than rejected
  spans and do not disproportionately come from generic headers.
- Two deterministic builds are byte-identical.

## Local acceptance criteria

1. 100/100 records produced and valid against raw LF input.
2. `raw_text[start:end] == entity.text` for every entity.
3. Full test suite passes.
4. No baseline record loses entities as a side effect.
5. A machine-readable audit reports additions by type, support count, model
   combination, record, and rejection reason.
6. Candidate output is not packaged as recommended if manual audit finds more
   than 15% obvious false positives in a stratified sample of additions.

## Black-box discipline

This experiment creates a submission candidate but does not submit it. The
leaderboard result, if the user chooses to submit, is external evidence. No
micro-variants will be generated from the same hypothesis without a causal
reason.
