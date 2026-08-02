# H41 analysis — queue construction

## Outcome

The prediction-blind queue construction gate passed. H41 is now waiting for
independent human labels; it has not trained a model or generated a submission.

| Measure | Result |
|---|---:|
| Unique passages | 60 |
| Development / holdout | 45 / 15 |
| Exact occurrences | 164 |
| Records represented | 59 |
| Characters directly reviewed | 20,055 |
| Characters after exact projection | 55,200 |
| Offset round-trip failures | 0 |
| Repository tests | 123 passed |

The main queue SHA-256 is
`a10b345aea2247cc5843e89894130f43279bd5bfc36c7bfda0c7abd357bd5f08`.
The 15-passage reviewer-2 queue SHA-256 is
`450cb52ca4da576709405d07e83c3c19325b837208c7353ac456bea6e3987f2d`.

## Feasibility amendment

The initial preregistration interpreted the earlier “15 groups with at least
four occurrences” census as 15 groups in at least four distinct records. The
implementation check found only 13 distinct-record groups because some lines
repeat twice inside one record. Before generating a queue or viewing a label,
the strata were amended from 15/15/30 to 13/17/30 and holdout allocation from
4/4/7 to 3/5/7. Total queue and holdout sizes did not change.

## Why work stops here

H39 and H40 show that neither correlated model votes nor repeated text alone can
identify the organizer's annotation policy. Training before H41 labels exist
would recreate the same circular pseudo-supervision. The next admissible action
is independent review, checksum lock, agreement/adjudication, then a one-shot
holdout comparison against frozen H38.
