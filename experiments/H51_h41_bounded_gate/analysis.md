# H51 — Distribution-free validity is vacuous at H41 scale

The repository metric proves each passage `final_score` is in `[0,1]`, so a
challenger-minus-baseline delta is exactly bounded by `[-1,1]`. H51 used that
fact to test two finite-sample lower bounds that do not rely on Normality:
global Hoeffding and a stratum-wise Maurer–Pontil empirical Bernstein bound.

## Analytic width

| Passages | Hoeffding penalty | Empirical Bernstein minimum penalty at zero variance |
|---:|---:|---:|
| 15 | 0.7013 | 6.6783 |
| 30 | 0.4959 | 2.8884 |
| 45 | 0.4049 | 1.8451 |
| 60 | 0.3507 | 1.3558 |

Hoeffding can promote at 15 passages only when the observed mean delta exceeds
0.7013 on a score whose full range is one point. The stratified empirical
Bernstein construction is even wider because the 2.5% error budget is split
across strata of only 3, 5, and 7 passages; its additive term alone exceeds
the entire delta range.

## Bounded-family stress result

Both methods have zero false promotions across five bounded null families and
10,000 replications per cell. That validity is not operationally useful. The
worst-family power is exactly zero for standardized effects `d=0.5`, `0.75`,
and `1.0` at every tested size from 15 through 60. Even at 60 passages,
Hoeffding's family-specific power at `d=0.75` ranges from 0 to 0.6544, while
empirical Bernstein never promotes any tested family/effect cell.

## Outer-loop decision

The small-sample statistical-repair branch is closed. Approximate methods
(H49–H50) either inflate Type-I or lose power/stability; guaranteed bounded
methods (H51) are valid but vacuous. H41 annotation remains valuable for
development and empirical error discovery. A future confirmatory design must
be registered only after label lock, using development data to specify a raw
effect scale and a genuinely larger independent holdout; it may not repurpose
the frozen 15 holdout or tune on its predictions.

Two reports are byte-identical at SHA-256
`2f8339727bb284339f9e5c689edd6d031b9cd1455e9284beb1bc27e0bedcb7ac`.
All 151 repository tests pass. No label, prediction, queue, evaluator, output
directory or ZIP changed.
