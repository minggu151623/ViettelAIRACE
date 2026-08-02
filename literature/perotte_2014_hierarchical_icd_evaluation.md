# Diagnosis code assignment: models and evaluation metrics

- **Authors:** Adler Perotte, Rimma Pivovarov, Karthik Natarajan, Nicole
  Weiskopf, Frank Wood, Noémie Elhadad
- **Year:** 2014
- **Venue:** Journal of the American Medical Informatics Association 21(2),
  231–237
- **DOI:** 10.1136/amiajnl-2013-002159
- **Primary source:** https://pmc.ncbi.nlm.nih.gov/articles/PMC3932472/

The study treats ICD assignment as hierarchical multi-label classification and
introduces metrics that distinguish same-subtree errors, overly coarse codes,
and overly granular codes. Its hierarchy-based SVM improved F-measure over a
flat baseline, but the authors emphasize that hierarchy-aware error meaning is
not captured by plain exact metrics alone.

**Project relevance.** Parent and specific codes are not interchangeable, and
blind ancestor closure can trade granularity for apparent coverage. H44 is thus
a targeted test of the organizer's annotation policy; H45 asks the separate
question of whether arbitrary ranked-prefix expansion improves the exact set
utility actually used by the competition.
