# H49 distributional robustness of H41 inference

| Independent passages | Type-I range | Worst power `d=0.5` | Worst power `d=0.75` |
|---:|---:|---:|---:|
| 15 | 0.0236–0.1126 | 0.5918 | 0.7950 |
| 30 | 0.0218–0.0704 | 0.7452 | 0.9352 |
| 45 | 0.0144–0.0574 | 0.8546 | 0.9806 |
| 60 | 0.0214–0.0582 | 0.9164 | 0.9916 |

Five passage-noise families were frozen with theoretical mean zero and unit
variance: Normal, Student-t(3), right-skew exponential, left-skew exponential,
and Rademacher. At 15 passages, right skew was conservative (0.0236 Type-I)
while left skew was anti-conservative (0.1126). The worst-family 80% power
count at `d=0.5` was 45 passages, not the Normal-only estimate of 30.

Raw evidence:
`experiments/H49_h41_power_robustness/results/power_envelope.json`. The repeat
is byte-identical at SHA-256
`ff40799312aa253bae637494909624b90ec41a801239b7581d22fbf22ee44f2e`.
