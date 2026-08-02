# Literature synthesis and project-specific adaptation

## Research finding

The useful pattern across the literature is not “ensemble eight unchanged
models.” It is a division of labour between proposal, retrieval, graph
structure and contextual disambiguation, with each component trained for the
target ontology.

## Primary sources

- [SapBERT](https://aclanthology.org/2021.naacl-main.334/) aligns synonyms of
  the same biomedical concept with metric learning. Its relevant mechanism is
  the self-alignment objective, not its English/UMLS checkpoint.
- [BioSyn](https://aclanthology.org/2020.acl-main.335/) combines sparse and
  dense representations and iteratively mines difficult candidates. This
  supports preserving character n-gram retrieval as a feature while the dense
  model learns semantic mismatch.
- [KRISSBERT](https://aclanthology.org/2022.findings-emnlp.61/) generates
  self-supervised mention examples from an ontology and trains a contextual
  encoder contrastively. This is directly relevant when organizer labels are
  absent.
- [ED-GNN](https://arxiv.org/abs/2104.01488) represents a mention as a query
  graph and uses graph-derived hard negatives; the authors report a 7.3% mean
  F1 improvement over prior methods on five datasets. This motivates
  same-family ICD and related-product RxNorm negatives.
- [BERGAMOT](https://aclanthology.org/2024.findings-naacl.288/) explicitly
  combines multilingual text and graph encoders with text, node-level
  contrastive and graph-information objectives. This is the closest match to
  the reported “semantic ontology + graph + classifier” recipe.
- [KEEP](https://proceedings.mlr.press/v287/elhussein25a.html) initializes from
  ontology structure, then adapts on clinical data under regularization that
  preserves ontology relationships. This motivates retaining a graph anchor
  while adapting to Vietnamese pseudo mentions.
- [DRAGON](https://aclanthology.org/2025.alta-main.18/) uses a three-stage
  bi-encoder, lexical-aware refinement and cross-encoder reranking pipeline.
  This supports a fast top-k retriever followed by explicit context/concept
  interaction rather than asking an LLM to select from the entire ontology.

## What is changed for this competition

Published checkpoints are mostly trained on English UMLS/MedDRA tasks and do
not implement the BTC entity taxonomy, Vietnamese clinical sections,
multilabel assertions, WHO ICD-10 2019 plus RxNorm CPC, or exact raw offsets.
H24 therefore changes the source architecture in five ways:

1. BamiBERT supplies only token representations; the previous NER head is not
   reused as the linker.
2. Mention/context and concept/path receive separate trainable projections.
3. A dependency-free relation-aware graph adapter consumes the exact local WHO
   and RxNorm graph rather than UMLS.
4. The pair classifier jointly predicts keep/drop, BTC type, concept
   compatibility and three independent assertions.
5. A structured decoder, external to the neural model, enforces exact offsets,
   valid codes and global span consistency.

## Stage-1 evidence

The deterministic graph contains 69,991 nodes and 294,548 typed edges. It uses
12,221 WHO ICD-10 nodes and 57,770 RxNorm CPC nodes; node and edge checksums are
recorded in `graph_manifest.json`.

A provenance-marked H23 weak-link set contains 518 unique mention/type/code
rows. Identical normalized mentions are kept within one fold, producing
426/36/56 train/dev/test rows. It is explicitly not organizer ground truth.

Character 2–5-gram TF-IDF against the complete graph reaches only:

| subset | R@1 | R@5 | R@10 |
|---|---:|---:|---:|
| overall | 10.81% | 14.09% | 16.80% |
| diagnosis | 2.62% | 5.00% | 6.90% |
| drug | 45.92% | 53.06% | 59.18% |

This shows why another dictionary/regex pass cannot be the breakthrough:
Vietnamese diagnosis mentions have almost no lexical overlap with English WHO
titles. It also supplies a low baseline that the dense+graph model must beat
under preregistered gates.

## Rejected shortcuts

- Do not download BERGAMOT/SapBERT and use it unchanged: ontology, language and
  entity schema differ.
- Do not use graph distance as a final score by itself: nearby concepts are
  often precisely the hard alternatives that require context.
- Do not label every H23-absent proposal as negative: hidden organizer entities
  may exist there, creating false-negative training collapse.
- Do not package a challenger before dense, graph and context ablations clear
  the frozen offline gates.

