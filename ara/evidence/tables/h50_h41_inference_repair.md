# H50 small-sample H41 inference repair

| Method | 15-passage Type-I range | Worst power `d=0.5` | Worst power `d=0.75` | Max nonfinite rate |
|---|---:|---:|---:|---:|
| Percentile | 0.0220–0.1132 | 0.5680 | 0.8010 | 0 |
| Stratified Welch-t | 0.0030–0.0724 | 0.3448 | 0.7042 | 0 |
| Bootstrap-t | 0.0084–0.0454 | 0.2880 | 0.5142 | 0.0462 |

Percentile fails maximum Type-I. Welch-t fails the minimum Type-I and power
requirements. Bootstrap-t fails minimum Type-I, power, and the 1% nonfinite
ceiling on Rademacher samples. No method was eligible and the H41 evaluator was
not changed. Raw evidence:
`experiments/H50_h41_inference_repair/results/method_comparison.json`.

The repeat is byte-identical at SHA-256
`d245368a99e5112888e636c18cdbd070f9863e56e2172e9312fd8fe621487582`.
