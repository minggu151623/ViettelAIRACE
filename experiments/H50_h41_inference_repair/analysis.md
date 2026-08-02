# H50 — No eligible small-sample repair for H41

H50 compared the current stratified percentile lower bound with a stratified
Welch-t bound and a stratified bootstrap-t bound on H49's five-family envelope.
The comparison was frozen before labels or model predictions were available.

## Fifteen-passage result

| Method | Type-I range | Worst power `d=0.5` | Worst power `d=0.75` | Max nonfinite rate |
|---|---:|---:|---:|---:|
| Percentile | 0.0220–0.1132 | 0.5680 | 0.8010 | 0 |
| Stratified Welch-t | 0.0030–0.0724 | 0.3448 | 0.7042 | 0 |
| Bootstrap-t | 0.0084–0.0454 | 0.2880 | 0.5142 | 0.0462 |

Percentile retains the most power but repeats H49's left-skew inflation.
Welch-t reduces the maximum false-promotion rate by 0.0408, yet falls below the
registered 0.01 minimum under right skew and retains only 0.3448 worst-family
power at `d=0.5`. Bootstrap-t controls the maximum rate most strongly but fails
both its minimum-rate and numerical-stability gates: 4.62% of Rademacher
replications produce a nonfinite bound, consistent with the literature's
discrete-sample warning.

At 30 passages, Welch-t becomes numerically stable with Type-I 0.0074–0.0608
and worst-family power 0.7204. At 45 passages it reaches 0.8432 power, but its
minimum Type-I remains 0.0074. These larger-n results are descriptive because
the registered selection rule concerns the frozen 15-passage holdout.

## Decision

No method is eligible, so `airace.h41_cluster_gate` remains unchanged. H41's
60 passages still have value for independent development, error analysis and
annotation-policy discovery, but the 15-passage holdout cannot serve as a
distribution-robust promotion test. Confirmatory use requires more independent
holdout passages or a separately justified bounded-data procedure; neither may
be retrofitted after predictions are opened.

The reports are byte-identical at SHA-256
`d245368a99e5112888e636c18cdbd070f9863e56e2172e9312fd8fe621487582`.
All 148 repository tests pass. No label, prediction, queue, evaluator or ZIP
was changed.
