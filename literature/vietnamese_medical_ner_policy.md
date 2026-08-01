# Independent evidence: Vietnamese medical NER label policy

## Sources reviewed 2026-07-27

- [ViMedNER paper](https://doi.org/10.4108/eetinis.v11i3.5221)
- [VietBioNER / Vietnamese biomedical NER corpus](https://aclanthology.org/2022.lrec-1.385/)
- [ViMQ paper](https://arxiv.org/abs/2304.14405)
- [ConText assertion detection](https://pmc.ncbi.nlm.nih.gov/articles/PMC2757457/)

## Findings relevant to Viettel AI Race

ViMedNER is close in domain but its published taxonomy is not identical to
the competition schema. It separates disease, symptom, cause, diagnostic, and
treatment. Its guideline explicitly says the same Vietnamese phrase can be a
symptom or a disease depending on context, and visible body-part manifestations
can be symptoms. Therefore a dictionary-only conversion from ViMedNER labels
to `CHẨN_ĐOÁN`/`TRIỆU_CHỨNG` would inject systematic type errors.

ViMQ uses a much coarser `SYMPTOM&DISEASE` category plus procedure and medicine.
It is useful for drug/symptom proposal recall but cannot supply the competition's
diagnosis-vs-symptom distinction without a context classifier.

The Vietnamese biomedical corpus uses a different set of categories again
(including symptom/disease and diagnostic procedure). This confirms that
external corpora are transfer sources, not reconstructed BTC ground truth.

The clinical assertion literature independently supports three orthogonal
dimensions: negation/certainty, temporality, and experiencer. This is consistent
with the competition's multilabel assertion field and argues against reducing
the list to a single mutually-exclusive label.

## Research decision

Do not merge these datasets directly into a submission. If used later, use them
to generate candidate spans only, then require competition-policy mapping and a
precision gate. No artifact was changed from this evidence.
