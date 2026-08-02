# Efficient set-valued prediction in multi-class classification

- **Authors:** Thomas Mortier, Marek Wydmuch, Krzysztof Dembczyński, Eyke
  Hüllermeier, Willem Waegeman
- **Year:** 2021
- **Venue:** Data Mining and Knowledge Discovery 35, 1435–1469
- **DOI:** 10.1007/s10618-021-00751-x
- **Primary source:** https://arxiv.org/abs/1906.08129

The paper frames prediction of a candidate set as Bayes utility maximization:
coverage of the true class must be balanced against a penalty that grows with
set size. For a broad family of utilities, the exact combinatorial search can
be reduced to evaluating prefixes of the probability-ranked classes. It also
shows why fixed top-k and arbitrary probability thresholds need not maximize
the intended set utility.

**Project relevance.** Viettel candidate output is explicitly set-valued and
scored by Jaccard. H45 therefore evaluates ranked prefixes using Jaccard itself
instead of treating recall@k as the optimization target. H24 lacks calibrated
conditional probabilities, so the paper supports the audit design but does not
license claiming its Bayes-optimal algorithm was implemented.
