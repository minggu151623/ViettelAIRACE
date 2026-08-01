# H4 — Multi-teacher consensus without gold labels

## Status

Exploratory and not yet approved for submission.

## Hypothesis

Independent proposal sources can provide a useful confidence signal. Agreement
between rule/dictionary, VietMed-NER, and LLM proposals should be safer than a
raw union, because union recall creates false positives under exact span/type
matching.

## Proposed design

1. Normalize each proposal to raw-text offsets.
2. Cluster proposals by exact span and compatible type.
3. Assign confidence from source agreement, section context, and lexical
   specificity.
4. Retain only high-confidence clusters.
5. Keep assertions and candidates in separate, auditable passes.

## Falsification

Reject if consensus cannot improve strict precision on an untouched split, or if
it changes more than one output dimension at once and the resulting leaderboard
movement cannot be attributed to a controlled ablation.

## Known warning

The current manual holdout was used during rule development, so it cannot serve
as an unbiased final test for this hypothesis.
