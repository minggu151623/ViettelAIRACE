# H1 — Text/type precision reconstruction

## Status

Protocol locked before execution. This is a confirmatory/diagnostic experiment,
not a leaderboard submission by itself.

## Hypothesis

Exact text score is the bottleneck. A precision-first reconstruction that
removes generic, nested, procedure, and unsupported spans while retaining
high-confidence clinical mentions will improve strict span/type quality more
reliably than adding model recall.

## Prediction

Compared with `output_v6_structural`, the candidate policy will remain unchanged,
assertion behavior will remain unchanged, and at least one of the following will
improve on the locked local holdout:

- strict span/type precision;
- strict span/type F1;
- number of schema/offset errors (must not increase).

If all improve by less than 1 percentage point or recall collapses by more than
5 points, reject the hypothesis.

## Controlled variables

- Same input files and raw text.
- Same assertion engine.
- Same candidate policy.
- Same output serializer and ZIP packaging.
- Only span/type acceptance rules may change.

## Procedure

1. Generate a fresh output directory from the current V6 source.
2. Run schema, offset, ordering, and duplicate validators.
3. Evaluate strict span/type metrics on the locked holdout.
4. Compare entity counts by type and per-record changes.
5. Repeat generation to verify byte identity.
6. Do not submit unless the local direction is positive and the change is
   explainable per record.

## Required artifacts

- `results/metrics.json`
- `results/per_record_diff.jsonl`
- `analysis.md`

## Failure modes to record

- span boundary drift;
- retyping a mention without changing its text;
- removal of an occurrence that is repeated at another position;
- accidental assertion/candidate changes;
- non-deterministic serialization.
