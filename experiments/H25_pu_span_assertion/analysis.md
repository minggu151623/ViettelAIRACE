# H25 analysis — positive-unlabeled span/type/assertion classifier

## Decision

Reject H25 as a submission path. Keep H23 frozen at 38.9352 and create no ZIP.

## Sanity and provenance

The first dry run exposed proposal paths from the previous input generation;
it produced zero H23 matches and was discarded before fitting the registered
context model. The protocol was corrected and committed before the valid run.
The valid corpus contains 7,412 exact proposal rows: 1,999 H23 matches and
5,413 unlabeled rows. H23 is an externally useful pseudo target, not organizer
ground truth.

## Span/type result

The registered dev rule selects contextual PU at threshold 0.95. Starting from
the frozen H20 simulation:

| Split | H20 strict F1 | H20 + H25 F1 | Gain | Addition precision |
|---|---:|---:|---:|---:|
| dev | 52.14% | 52.53% | +0.39 pp | 41.67% |
| test | 55.95% | 56.35% | +0.40 pp | 36.84% |

The perfect-label oracle over exactly the same disjoint proposal pool reaches
59.78% dev and 63.01% test, gains of 7.64 and 7.06 points. The pool therefore
contains useful spans, but source votes, confidence and Qwen context do not
separate them reliably under the current weak supervision.

## Assertion result

Qwen context raises assertion macro Jaccard on test from 76.68% to 80.57%, but
lowers dev from 82.27% to 79.24%. This sign reversal fails the registered
two-split gate. The deterministic assertion engine remains the fallback.

## Mechanistic failure

Seventeen H23-absent rows satisfy the nominal two-source, probability and bag
stability filter, yet obvious correlated model errors remain, including
`doxycyclinebactrim`, `klonopinclonidine`, `ảo giácxuất`, `buồn`, and `đoạn`.
The Bami variants share boundary failure modes, so agreement and low bagging
variance are not independent evidence. PU calibration cannot repair a proposal
generator whose teachers make correlated errors.

## Next direction

Do not tune PU thresholds. First test record-held-out annotation-policy
distillation from H23: a train-record-only high-purity phrase lexicon provides
an independent proposal source. If that broadens held-out coverage, combine it
with a direct LLM extractor or semantic verifier; otherwise the current
proposal family is closed.
