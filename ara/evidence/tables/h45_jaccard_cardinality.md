# H45 Jaccard-aware cardinality evidence

Label status: H24 weak pseudo-labels, not organizer ground truth.

| Policy | Test macro-Jaccard | Delta vs top-1 |
|---|---:|---:|
| Singleton top-1 | 0.178571 | — |
| Global dev-selected (`k=1`) | 0.178571 | 0.000000 |
| Type-specific dev-selected (`k=1`, `k=1`) | 0.178571 | 0.000000 |
| Fixed `k=2` | 0.107143 | -0.071429 |
| Fixed `k=5` | 0.060119 | -0.118452 |
| Fixed `k=10` | 0.039123 | -0.139448 |
| Per-row prefix oracle (diagnostic only) | 0.233099 | +0.054528 |

The preregistered type-specific comparison has paired-bootstrap delta 0 with
95% interval `[0, 0]` over 10,000 resamples. The promotion gate failed; no ZIP
was allowed or created. Raw evidence:
`experiments/H45_jaccard_cardinality_audit/results/report.json`.
