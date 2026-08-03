# Cross-lingual clinical NER projection — evidence note for H64

## Primary sources

1. Yang et al. (2022), **CROP: Zero-shot Cross-lingual Named Entity Recognition
   with Multilingual Labeled Sequence Translation**.
   https://aclanthology.org/2022.findings-emnlp.34/
   - Pipeline: translate target text into a source language, tag with a source
     NER model, then project a labeled sequence back into the target language.
   - The paper reports gains over strong zero-shot baselines, but explicitly
     identifies translation/projection noise as the central failure mode.

2. Jain et al. (2019), **Entity Projection via Machine Translation for
   Cross-Lingual NER**.
   https://aclanthology.org/D19-1100/
   - Improves projection by translating both sentences and entities, then
     matching with orthographic/phonetic and corpus-level evidence.
   - This motivates H64's sentence translation + entity back-translation and
     mutual target-span match rather than one-way token alignment.

3. Gaschi et al. (2023), **Multilingual Clinical NER: Translation or
   Cross-lingual Transfer?**
   https://aclanthology.org/2023.clinicalnlp-1.34/
   - In clinical NER, translation-based methods can approach cross-lingual
     transfer, but design details matter and domain-specific monolingual models
     do not automatically beat large multilingual models.
   - H64 therefore compares multiple English model families and calibrates on
     public clinical gold before touching Turn 2.

4. Politov et al. (2025), **Revisiting Projection-based Data Transfer for
   Cross-Lingual Named Entity Recognition in Low-Resource Languages**.
   https://aclanthology.org/2025.nodalida-1.54/
   - Back-translation can refine alignments, and formal matching of projected
     entities to target candidates improves projection quality.
   - H64 uses back-translation agreement and exact raw-span candidate matching
     as mandatory confidence features.

## Synthesis for this project

The project already has several correlated Vietnamese proposal families. H39
showed that their votes are not interchangeable noisy labels, while H58 showed
that a broad new LLM recall source can regress all leaderboard components. The
literature does not justify raw translation-view union. It justifies a new,
independent proposal family whose projection precision is measured first.

H64 therefore has three defenses:

1. public-source calibration on Vietnamese gold before Turn-2 inference;
2. two English NER families plus bidirectional projection agreement;
3. conservative fusion into frozen H38, with explicit fragment, ontology and
   repeated-passage consistency gates.

Expected value is not guaranteed. Translation projection is a worthwhile pivot
because it changes the evidence family and makes English ontology linking much
easier, not because a paper's F1 gain transfers directly to this competition.
