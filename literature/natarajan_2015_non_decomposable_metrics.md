# Optimal decision-theoretic classification using non-decomposable metrics

- **Authors:** Nagarajan Natarajan, Oluwasanmi Koyejo, Pradeep Ravikumar,
  Inderjit S. Dhillon
- **Year:** 2015
- **Primary source:** https://arxiv.org/abs/1505.01802

The paper analyzes expected out-of-sample utility for non-decomposable metrics,
including Jaccard and F-measure. Its probability-ranking result establishes that
optimizing these utilities is not equivalent to optimizing independent example
or label decisions; calibrated conditional probabilities and a metric-aware
decision rule are required.

**Project relevance.** Candidate recall@k cannot stand in for candidate
Jaccard. This motivates H45's direct per-row Jaccard computation and prevents a
retrieval improvement from automatically authorizing a longer candidate list.
