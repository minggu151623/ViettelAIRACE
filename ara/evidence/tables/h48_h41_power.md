# H48 power of the H41 passage-clustered gate

| Independent passages | Type-I (`d=0`) | Power `d=0.25` | Power `d=0.5` | Power `d=0.75` | Power `d=1.0` |
|---:|---:|---:|---:|---:|---:|
| 15 | 0.0530 | 0.2460 | 0.5882 | 0.8748 | 0.9780 |
| 30 | 0.0350 | 0.3028 | 0.8034 | 0.9866 | 0.9998 |
| 45 | 0.0322 | 0.4112 | 0.9210 | 0.9986 | 1.0000 |
| 60 | 0.0338 | 0.5050 | 0.9736 | 1.0000 | 1.0000 |

The preregistered 15-passage Type-I gate passes and the `d=0.5` power gate
fails. On the frozen grid, the 15-passage minimum detectable effect at 80%
power is `d=0.75`; 30 passages are needed at `d=0.5`. Rates use 5,000
replications and 1,000 stratified bootstrap iterations per replication under
independent Normal(`d`, 1) passage deltas. Raw evidence:
`experiments/H48_h41_power_curve/results/power.json`.

The repeat result is byte-identical at SHA-256
`b6f9dbf5056a8b8523d0e7678557f69e8ae62ebf374dabfc7ee0f5e34d85e773`.
