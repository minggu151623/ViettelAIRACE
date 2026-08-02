# H51 finite-sample bounded H41 gates

| Passages | Hoeffding penalty | Empirical Bernstein zero-variance penalty | Worst power through `d=1` |
|---:|---:|---:|---:|
| 15 | 0.7013 | 6.6783 | 0 |
| 30 | 0.4959 | 2.8884 | 0 |
| 45 | 0.4049 | 1.8451 | 0 |
| 60 | 0.3507 | 1.3558 | 0 |

The competition-style passage final score is in `[0,1]`; a paired challenger
delta is therefore in `[-1,1]`. Both finite-sample methods had zero false
promotions over the frozen bounded stress families, but both usefulness gates
failed. No evaluator change was installed. Raw evidence:
`experiments/H51_h41_bounded_gate/results/bounded_gate.json`.

The repeat is byte-identical at SHA-256
`2f8339727bb284339f9e5c689edd6d031b9cd1455e9284beb1bc27e0bedcb7ac`.
