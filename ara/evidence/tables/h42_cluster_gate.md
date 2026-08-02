# H42 correlated-null promotion audit

Frozen design: 15 unique holdout passages, 41 exact occurrences, 10,000 null
replications and 1,000 percentile bootstraps per replication.

| Within-passage rho | Occurrence false promotion | Passage-cluster false promotion | Reduction |
|---:|---:|---:|---:|
| 0.0 | 2.95% | 5.18% | -2.23 pp |
| 0.3 | 6.78% | 5.25% | 1.53 pp |
| 0.6 | 10.55% | 5.43% | 5.12 pp |
| 0.9 | 13.28% | 5.10% | 8.18 pp |

Both preregistered reductions passed. Source report:
`experiments/H42_h41_cluster_gate/results/null_simulation.json`, reproducible
file SHA-256 `2e62fc1e3ae59b173653030007803d451d2a7ab7252bd56e2bc84a2942a94efa`.
