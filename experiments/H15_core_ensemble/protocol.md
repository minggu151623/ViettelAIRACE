# H15 — Evidence-preserving specialist core

## Classification

Confirmatory infrastructure experiment. This does not create a submission
artifact and does not claim a leaderboard improvement.

## Motivation

The current ensemble path discards `confidence` and `source` when model output
is serialized through the competition schema. As a result, downstream merging
can only use fixed ownership, overlap, and length. That is insufficient for the
type-specialist ensemble suggested by the near-zero text score and the
directional peer report about a multi-model core.

## Intervention

1. Introduce a non-submission `Proposal` schema that retains:
   span text, type, offsets, model confidence, source, assertions, and
   candidates.
2. Keep the competition JSON unchanged.
3. Add an optional proposal-sidecar directory to VietMed-NER inference.
4. Verify round-trip preservation, deterministic serialization, and unchanged
   competition entities.

## Frozen controls

- No H7 submission JSON is changed.
- No CRLF coordinate projection is applied at proposal generation.
- No proposal is added to a submission by this experiment.
- No confidence threshold is tuned against leaderboard results.
- Existing detector and reference-merging behavior is unchanged.

## Predictions

- Proposal sidecars preserve exact floating-point confidence and source labels.
- Converting a sidecar proposal back to an `Entity` produces the same
  competition dictionary as the original entity.
- The full test suite remains green.
- The CLI exposes proposal export without changing its default behavior.

## Decision rule

Keep the infrastructure only if all predictions hold. The next H15 stage may
use it to build per-model proposal banks, but a merged submission remains
blocked until a reviewed calibration set and a preregistered merger evaluation
exist.
