# H68 literature note — RxNorm exact drug linking

## Official terminology evidence

- NLM describes RxNorm as a normalized naming system for generic and branded
  drugs. The Current Prescribable Content (CPC) contains active normalized
  names, RxCUIs, attributes and relationships in `RXNCONSO`, `RXNSAT` and
  `RXNREL` and is downloadable without a UMLS license.
  - https://www.nlm.nih.gov/research/umls/rxnorm/docs/prescribe.html
  - https://www.nlm.nih.gov/research/umls/rxnorm/docs/rxnormfiles.html
- RxNorm term types distinguish ingredients, brands, clinical drugs, branded
  drugs, dose forms and prescribable synonyms. Relations connect ingredients,
  brands and products; these relations justify structured fields and also
  create difficult same-family negatives rather than interchangeable codes.
  - https://www.nlm.nih.gov/research/umls/rxnorm/sourcereleasedocs/rxnorm.html
  - https://www.nlm.nih.gov/research/umls/rxnorm/docs/techdoc.html

## Modeling evidence

- SapBERT learns biomedical concept representations from same-concept synonym
  pairs. This supports using official same-RxCUI strings as representation
  supervision rather than H38 predictions.
  - https://aclanthology.org/2021.naacl-main.334/
- CODER-style contrastive entity linking uses terminology structure and hard
  negatives, motivating ingredient-family-held-out evaluation and explicit
  wrong-product negatives.
  - https://aclanthology.org/2022.findings-emnlp.61/
- A two-stage alias-retrieval plus LLM/context disambiguation design can improve
  biomedical linking, but the target action still needs calibrated abstention.
  - https://aclanthology.org/2025.acl-short.25/
- ANGEL reports that explicitly training against hard negative entity outputs
  improves biomedical entity linking, supporting H68's same-ingredient wrong
  strength/form/route negatives.
  - https://aclanthology.org/2025.findings-acl.558/

## Consequence for H68

The evidence supports a narrow exact-linking experiment, not arbitrary ontology
expansion. The unit of truth is the RxCUI and its official synonym/relationship
structure. Ingredient-related products are useful hard negatives whenever the
task requires the exact product. H68 therefore emits a singleton or abstains,
and it freezes all spans, assertions and ICD candidates.
