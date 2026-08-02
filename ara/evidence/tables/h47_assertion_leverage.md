# H47 novel-span assertion leverage

| Stage | Novel keys | Asserted novel | Records | Assertion J delta | Weighted observed loss |
|---|---:|---:|---:|---:|---:|
| H37 vs H23 | 26 | 7 | 6 | -0.1301 | 0.03903 |
| H38 vs H37 | 183 | 29 | 18 | -0.0234 | 0.00702 |
| Combined | 209 | 36 | 18 unique | — | 0.04605 |

Assertion labels across the 36 entities are `isHistorical` 27, `isNegated` 7,
and `isFamily` 2. Recurrence, count and record-coverage gates pass; the frozen
0.10 observed-leverage gate fails. This quantity is not a counterfactual upper
bound. No altered directory or ZIP was created. Raw evidence:
`experiments/H47_novel_span_assertion_leverage/results/report.json`.
