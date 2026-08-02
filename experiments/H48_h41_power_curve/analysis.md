# H48 — Power limit of the frozen H41 holdout

H42 showed that the passage-stratified bootstrap controls false promotion when
repeated occurrences are correlated. H48 asks the separate question: is the
frozen 15-passage holdout sensitive enough to make a negative result informative?

## Result

The Type-I gate passes at 0.053 for 15 passages, close to the nominal 0.05.
The moderate-effect power gate fails: at standardized passage-level effect
`d=0.5`, promotion occurs in only 0.5882 of 5,000 replications. On the frozen
effect grid, 15 passages reach 80% power only at `d=0.75` (0.8748). Doubling
the same stratum proportions to 30 independent passages reaches 0.8034 power
at `d=0.5`.

| Independent passages | Type-I (`d=0`) | Power `d=0.25` | Power `d=0.5` | Power `d=0.75` |
|---:|---:|---:|---:|---:|
| 15 | 0.0530 | 0.2460 | 0.5882 | 0.8748 |
| 30 | 0.0350 | 0.3028 | 0.8034 | 0.9866 |
| 45 | 0.0322 | 0.4112 | 0.9210 | 0.9986 |
| 60 | 0.0338 | 0.5050 | 0.9736 | 1.0000 |

Small effects remain difficult: `d=0.25` reaches only 0.505 power even at 60
passages. These rates are model-based sensitivity diagnostics, not guarantees
for the eventual labeled data.

## Decision

H41 remains a valid high-effect confirmation gate, not an equivalence test. A
non-promotion on its holdout cannot establish that H38 and a challenger are
equivalent or that a moderate effect is absent. The frozen queue and split are
unchanged; any future expansion to 30 or more independent passages requires a
separate preregistration and new prediction-blind selection.

The two deterministic result files are byte-identical. Result SHA-256:
`b6f9dbf5056a8b8523d0e7678557f69e8ae62ebf374dabfc7ee0f5e34d85e773`.
All 142 repository tests pass.
