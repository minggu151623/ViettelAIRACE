# H49 — Distributional robustness of H41 power

H48's Normal model was informative but not robust enough to size a future
queue. H49 preserves zero mean and unit variance while changing only the shape
of passage-level noise across Normal, Student-t(3), right-skew exponential,
left-skew exponential, and Rademacher families.

## Main result

The percentile bootstrap is distribution-sensitive at H41's frozen sample
size. At 15 passages, Type-I rates span 0.0236–0.1126. Right skew is
conservative (0.0236), while left skew is anti-conservative (0.1126). Thus
H42's near-5% correlated-Normal result does not guarantee Type-I control for
asymmetric passage deltas.

| Passages | Type-I range | Worst power `d=0.5` | Worst power `d=0.75` |
|---:|---:|---:|---:|
| 15 | 0.0236–0.1126 | 0.5918 | 0.7950 |
| 30 | 0.0218–0.0704 | 0.7452 | 0.9352 |
| 45 | 0.0144–0.0574 | 0.8546 | 0.9806 |
| 60 | 0.0214–0.0582 | 0.9164 | 0.9916 |

H48's Normal estimate that 30 passages reach 80% power at `d=0.5` is not
robust: the left-skew family reaches only 0.7452. The distributional envelope
first clears 80% at 45 passages (0.8546). For `d=0.75`, the robust count is 30,
because the left-skew 15-passage power is 0.7950.

## Decision

The qualitative conclusion survives—15 passages are a high-effect screen, not
an equivalence test—but the numerical recommendation changes. Do not claim
that 30 passages suffice for moderate effects. Before labels are opened, the
promotion method needs a separate preregistered small-sample robustness repair;
otherwise H41's lower percentile bound must be reported as distribution-
sensitive and not treated as a universal 5% test.

The queue, labels, predictions, model outputs and H44 ZIP were untouched. Two
complete reports are byte-identical at SHA-256
`ff40799312aa253bae637494909624b90ec41a801239b7581d22fbf22ee44f2e`.
All 145 repository tests pass.
