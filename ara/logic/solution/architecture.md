# Architecture

V16 retains V6 as the precision anchor for existing entities, assertions, and
RxNorm. A class-balanced BamiBERT student proposes spans. The original medical
NER checkpoint acts as an independent label-space teacher. Only high-confidence
same-type overlaps are added, and additions may not overlap V6. Diagnosis ICD
candidates remain empty because prior external evidence showed candidate
stripping improved the score.

## H24 ontology-graph contextual core

H24 replaces post-hoc candidate lookup with five connected stages: a
heterogeneous proposal pool, a typed WHO/RxNorm graph, a sparse+dense dual
encoder, a context/concept pair classifier, and a global structured decoder.
BamiBERT is only the token backbone. Mention and concept text use separate
projection heads; a custom relation-aware adapter aligns concept embeddings to
the local graph. The classifier predicts keep/drop, BTC type, concept
compatibility and three independent assertions. Candidate IDs remain
ontology-constrained and exact raw offsets are enforced outside the model.
