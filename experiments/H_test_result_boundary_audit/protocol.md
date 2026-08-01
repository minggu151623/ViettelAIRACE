# H14 protocol — numeric laboratory name/result split

## Status

PREREGISTERED, artifact not generated.

## Hypothesis

For high-confidence laboratory rows, BTC expects an independent
`TÊN_XÉT_NGHIỆM` span and a `KẾT_QUẢ_XÉT_NGHIỆM` span containing only the value
plus an explicitly present unit. V6's compound `name + value` result spans
therefore lose text/type credit.

## Isolated intervention

Starting from `output_v6_structural_btc`:

1. detect only numeric result spans whose leading/trailing text contains a
   high-confidence test-name lexicon item;
2. split at the name/value boundary;
3. retain the exact value and unit substring in the result;
4. add the test-name entity only when it is not already present at that exact
   position;
5. leave all diagnosis/symptom/drug spans, assertions, candidates, and positions
   outside the edited lab rows unchanged.

Do not rewrite textual imaging descriptions, negative phrases, or ambiguous
multi-value panels in the first test.

## Pre-run checks

- `raw_text[start:end] == text` for every entity;
- no duplicate exact `(type, position)` records;
- deterministic byte identity on rerun;
- diff contains only the targeted lab rows;
- candidate and assertion fields are byte-identical outside edited rows.

## Local measurements

- strict span/type precision and recall on the manually curated holdout;
- count of split rows and accidental splits;
- schema/offset error count;
- per-type entity count delta.

## External decision rule

Do not submit automatically. A user may choose the artifact only if:

- the local holdout improves strict test-name/result boundary F1 without
  reducing other-type precision; and
- H7's position-only measurement has already been resolved or explicitly
  deprioritized.

If submitted, it must be a single-axis H14 artifact, not a combination with
H7, H13, H8, or candidate changes.

The candidate rows requiring manual review are listed in
`experiments/H_test_result_boundary_audit/review_queue.md`. This queue is a
review aid, not organizer gold and not a source for hidden-label reconstruction.
