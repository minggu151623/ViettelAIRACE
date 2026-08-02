# H46 score-shape cardinality evidence

Label status: H24 weak pseudo-labels, not organizer ground truth.

| Quantity | Result | Gate |
|---|---:|---:|
| Reproduced diagnosis rankings | 420/420 | pass |
| Dev top-1 Jaccard | 0.071429 | baseline |
| Dev adaptive Jaccard | 0.089286 | — |
| Dev delta | +0.017857 | fail (≥0.02) |
| Paired-bootstrap 95% interval | [0.000000, 0.053571] | fail (lower >0) |
| Mean selected k | 3.107143 | fail (≤3) |
| Test | canceled | protocol |

The selected alpha was 0.1. Five of 28 development rows received `k=9` or
`k=10`, indicating unstable expansion. Repeat JSON reports are byte-identical
at SHA-256 `58573af96d2f6a3589ede0939be8bfd650335e2d6db7bdd9aaa8711c5745c8f5`.
No ZIP was permitted or created.
