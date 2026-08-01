# i2b2/VA policy as an independent prior

## Primary sources

- [2010 i2b2/VA documentation](https://www.i2b2.org/NLP/Relations/Documentation.php)
- [Challenge task and assertion description](https://pmc.ncbi.nlm.nih.gov/articles/PMC3168311/)
- [Comparison of i2b2 concept-boundary guidelines](https://pmc.ncbi.nlm.nih.gov/articles/PMC3599895/)
- [Evaluation methods](https://www.i2b2.org/NLP/Relations/assets/Evaluation%20methods%20for%202010%20Challenge.pdf)

## Structural correspondence

The competition schema is consistent with an adaptation of the 2010 i2b2/VA
clinical information-extraction task:

| i2b2 | Viettel schema |
|---|---|
| problem | split into `CHẨN_ĐOÁN` and `TRIỆU_CHỨNG` |
| test | split into `TÊN_XÉT_NGHIỆM` and `KẾT_QUẢ_XÉT_NGHIỆM` |
| treatment | narrowed mainly to `THUỐC` |
| absent | `isNegated` |
| associated with someone else | `isFamily` |
| present | empty assertion list |
| document section/temporality | `isHistorical` |

This is a research hypothesis, not proof of data provenance. BTC explicitly
uses multilabel assertions and applies history to drugs, whereas original
i2b2 assertion labels are mutually exclusive and formally assigned only to
problem concepts.

## Boundary priors worth retaining

The i2b2 guideline evidence says:

- annotate each occurrence separately;
- include a body-part prepositional phrase when it forms one clinical concept;
- split independent symptom lists into separate concepts;
- keep conjunctions inside one concept only when the conjuncts share modifiers;
- do not annotate concepts unrelated to the patient.

These rules agree with BTC's repeated-occurrence answer and with examples such
as body-part symptoms. They are useful priors for independent annotation, but
must yield to explicit BTC evidence wherever the schemas differ.

## Consequence

Do not train an i2b2 model and map labels mechanically. Use the guideline only
to standardize manual Vietnamese span boundaries and context attributes. The
diagnosis-vs-symptom and test-name-vs-result splits still require competition-
specific annotation.
