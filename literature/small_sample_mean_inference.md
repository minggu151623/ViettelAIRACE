# Small-sample mean inference under skewness

## Sources

1. Efron, B. (2003), *Second Thoughts on the Bootstrap*, Statistical Science
   18(2), 135–140. The review distinguishes second-order bootstrap-t/BCa
   methods from standard intervals but explicitly warns that nonparametric
   bootstrap intervals can remain far from exact in small samples.
   https://projecteuclid.org/journals/statistical-science/volume-18/issue-2/Second-Thoughts-on-the-Bootstrap/10.1214/ss/1063994968.full
2. Owen, A. B. (2025), *Better bootstrap t confidence intervals for the mean*.
   The paper reports good coverage for usual bootstrap-t but documents long or
   infinite intervals for discrete samples; weighted beta bootstrap-t improves
   this tradeoff. https://arxiv.org/abs/2508.10083
3. Maurer, A. and Pontil, M. (2009), *Empirical Bernstein Bounds and Sample
   Variance Penalization*, COLT. The paper provides non-asymptotic,
   variance-sensitive confidence bounds for bounded variables, but those bounds
   target guaranteed validity rather than high power at very small n.
   https://arxiv.org/abs/0907.3740
4. Wang, W., Yu, C., and Zhang, Z. (2024), *On the Assessment of Bootstrap
   Intervals for Samples of Fixed Size*. Exact fixed-n calculations show that
   common bootstrap intervals need not achieve their nominal confidence
   coefficient. https://arxiv.org/abs/2402.09397

## Relevance to H41

H49 reproduces the literature's small-sample warning: percentile bounds become
anti-conservative under left skew. H50 will therefore compare the frozen
percentile method against a studentized bootstrap and a stratified Welch-style
t bound. It will record bootstrap-t degeneracy rather than silently replacing
infinite statistics. No literature source establishes exact finite-sample
validity for either approximate repair across H41's unknown delta law, so the
choice remains simulation-calibrated and must stay prediction-blind.

Empirical Bernstein is not placed in H50's primary comparison because H49's
stress families are unbounded, violating its premise. It remains a possible
fully bounded fail-safe after the actual score-delta scale and desired power
tradeoff are specified.
