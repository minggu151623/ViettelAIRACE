# H42 analysis — cluster-aware H41 promotion gate

## Outcome

H42 passed both preregistered correlated-null gates. Treating the 41 holdout
occurrences as independent becomes strongly anti-conservative as exact copies
share more of their error. Resampling the 15 unique passages within the frozen
high/middle/low strata remains near a 5% one-sided false-promotion rate.

| Within-passage correlation | Occurrence bootstrap | Passage-cluster bootstrap | Reduction |
|---:|---:|---:|---:|
| 0.0 | 2.95% | 5.18% | -2.23 pp |
| 0.3 | 6.78% | 5.25% | 1.53 pp |
| 0.6 | 10.55% | 5.43% | 5.12 pp |
| 0.9 | 13.28% | 5.10% | 8.18 pp |

The full 10,000-replication, 1,000-bootstrap-per-replication report is
byte-identical across two runs (SHA-256
`2e62fc1e3ae59b173653030007803d451d2a7ab7252bd56e2bc84a2942a94efa`).

## Consequence for H41

The older `airace.blind_eval` evaluates complete records and cannot be used for
H41's passage-local labels. The new evaluator scores only exact labeled passage
windows, rejects predictions crossing a passage boundary, aggregates assertion
scores inside their passage, and bootstraps unique passages within frozen
strata. It reports occurrence-weighted effects only as descriptive statistics.

This repairs the promotion gate before either reviewer label file exists. H41
remains blocked on independent annotation; no model prediction, output artifact
or leaderboard submission was exposed or created.
