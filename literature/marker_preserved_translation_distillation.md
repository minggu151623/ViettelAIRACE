# Marker-preserved translation distillation for H66

H65 established two independent bottlenecks: English model agreement before
projection was sparse, and literal string projection back to Vietnamese had
zero yield. H66 therefore moves translation out of target inference and uses it
only to manufacture span-exact Vietnamese supervision.

## Primary evidence

- CROP translates the target sequence to a source language, applies a source
  NER model, then uses labeled-sequence translation to project labels back.
  Its central lesson for H66 is that label-aware sequence generation is a
  different interface from searching the raw target for translated strings:
  https://aclanthology.org/2022.findings-emnlp.34/
- SimAlign shows that contextual multilingual representations can support word
  alignment without task-specific parallel training. H66 keeps alignment as a
  diagnostic/fallback for synthetic QA, not as the Turn2 output interface:
  https://aclanthology.org/2020.findings-emnlp.147/
- Entity Projection via Machine Translation combines sentence/entity
  translation and multiple matching signals; it supports treating entity
  translation separately from sentence translation:
  https://aclanthology.org/D19-1100/
- The multilingual clinical NER comparison shows that translation-based
  transfer can approach cross-lingual transfer when the translation design is
  controlled; it does not establish that an unmodified translation pipeline is
  safe for BTC:
  https://aclanthology.org/2023.clinicalnlp-1.34/

## Falsifiable claim

Synthetic data is useful only if it improves two direct Vietnamese students
over identical direct-data controls on untouched public development and test
sets. Marker integrity alone is insufficient. If the treatment does not produce
a stable held-out gain, H66 stops before Turn2 and the research claim is
rejected.

The target merger additionally isolates two externally observed risks. H58
showed that changing entity identity can reduce candidate Jaccard even when old
candidate fields are frozen, so H66 merges a new diagnosis or drug only with one
unique supported ontology code. Assertions are empty only for mentions outside
negation, history and family scopes; uncertain mentions remain shadow-only.
