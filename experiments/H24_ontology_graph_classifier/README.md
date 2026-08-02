# H24 ontology-graph contextual classifier

## Status

Preregistered before generating training pairs, fitting a model, selecting
thresholds, or producing a submission artifact.

## Frozen fallback

`turn2/output_v8_candidate_semantic.zip`, externally scored 38.9352 with WER
57.2161, assertion Jaccard 47.5455, and candidate Jaccard 29.5910.

## Motivation

H23 changed 144 defensible ICD candidate lists but gained only 0.1376 and left
text/assertion metrics frozen. Candidate-list post-processing is therefore
valid but not a breakthrough axis. The next core must jointly decide whether a
span is an entity, its type, and its ontology concept from local context.

The design adapts five research mechanisms rather than copying a published
checkpoint:

1. SapBERT-style synonym self-alignment for medical concept representations.
2. BioSyn-style sparse+dense retrieval with model-mined hard negatives.
3. KRISSBERT-style contextual mention prototypes generated without organizer
   labels.
4. BERGAMOT/ED-GNN-style ontology graph objectives and graph hard negatives.
5. DRAGON-style bi-encoder retrieval followed by explicit cross-encoder
   interaction and lexical-aware reranking.

## Registered architecture

### A. Proposal layer

Take the union of H23 entities, H20 entities, and the three frozen Turn-2 model
proposal banks. This is only a candidate pool; raw union is never a submission.
Every row retains source count, source confidence, exact/overlap evidence,
section, boundary shape, and local context.

### B. Ontology graph

Build typed concept graphs from the frozen WHO ICD-10 2019 hierarchy and
RxNorm CPC relations. Nodes carry code, canonical term, aliases, concept type,
and ancestor path. Edges include synonym, parent/child, sibling-via-parent, and
the supported RxNorm ingredient/product relations. No UMLS-only edge or
unlicensed resource may be assumed.

### C. Retrieval encoder

Start from the locally available Vietnamese BamiBERT encoder and modify its
training source: mention/context and concept/path use separate projections.
Train with a weighted sum of:

- synonym/alias contrastive loss;
- mention-to-concept contrastive loss from high-confidence pseudo pairs;
- parent/child graph alignment loss;
- type-separation loss;
- hard-negative loss using same-family ICD siblings and lexically similar
  RxNorm products.

Candidate retrieval fuses character n-gram similarity with dense cosine
similarity. Sparse and dense weights are fitted only on a frozen training
partition; no leaderboard score is used as a threshold.

### D. Context classifier/reranker

For each proposed span and top-k concept, score an explicit pair containing
section, left context, marked mention, right context, entity type, canonical
concept text and ancestor path. The classifier predicts:

- keep/drop;
- one of the six BTC entity types;
- concept compatibility;
- three assertion labels as independent sigmoid outputs.

Candidate IDs are restricted to the retrieved ontology nodes, so the model
cannot invent a code. Graph distance, lexical score, dense score, source votes,
and cross-encoder score are classifier features rather than hand-set final
thresholds.

### E. Structured decoder

Use weighted interval scheduling to select a globally consistent non-overlap
set. Preserve distinct repeated occurrences. Candidate output remains top-1,
or parent+specific top-2 only when both graph and classifier support the pair.
All offsets must satisfy `raw_text[start:end] == text`.

## Training evidence tiers

- Tier A positive: exact H23/H20 agreement or exact agreement of H23 with at
  least two frozen model banks.
- Tier B positive-unlabeled: H20-only/H23-only rows and exact two-model rows.
  These are never treated as clean negatives.
- Negative: malformed offsets, impossible type/section combinations, or
  ontology hard negatives for an otherwise positive mention.
- Organizer ground truth is absent; H22/H23 pseudo rows must be identified as
  weak labels in every report.

## Frozen evaluation

1. Split concept aliases by canonical concept so an evaluated alias is never
   present verbatim in the training side of that fold.
2. Report lexical-only, dense-only, dense+graph and full-reranker Recall@1/5/10.
3. Report a separate same-family/sibling hard-negative accuracy.
4. Use record-level cross-validation for span keep/type classification and
   report strict span/type precision, recall, F1 and calibration error.
5. Run ablations that remove graph loss, context and hard negatives.
6. Validate 100/100 JSON files, deterministic reruns and all repository tests.

## Promotion gate

H24 may produce a challenger ZIP only if all of the following hold:

- full retrieval improves alias-held-out Recall@1 by at least 5 absolute
  points and Recall@5 by at least 8 points over lexical-only;
- graph+hard-negative accuracy improves by at least 5 points over the same
  encoder without graph features;
- record-level span/type F1 exceeds the strongest frozen single proposal model
  and no entity type loses more than 2 F1 points;
- an ablation demonstrates that graph or context contributes independently;
- no ontology contradiction, invalid offset, duplicate entity, or invented
  candidate appears in a full-corpus audit;
- the change set is architecture-scale and its score is not selected using an
  H22/H23 in-sample proxy.

If any gate fails, H23 remains the fallback and no leaderboard submission is
recommended. The competition is never submitted automatically.

## Registered implementation order

1. Build and test the typed WHO/RxNorm graph.
2. Create alias-held-out and record-held-out datasets with provenance.
3. Establish lexical and current-encoder baselines.
4. Train the graph-aligned dual encoder.
5. Train the contextual classifier/reranker.
6. Run frozen ablations and only then decide whether to package a challenger.

## Stage-1 implementation result

- Added a deterministic typed graph builder for WHO ICD-10 and RxNorm CPC.
- Built 69,991 nodes and 294,548 edges with stable node/edge checksums.
- Built 518 unique provenance-marked weak mention/concept rows with alias-group
  426/36/56 train/dev/test splits.
- Established a complete-ontology character TF-IDF baseline: overall R@1
  10.81%, diagnosis R@1 2.62%, and drug R@1 45.92%.
- Implemented the customized neural core: separate mention/concept projections,
  relation-aware graph adapter, graph hard-negative loss, contextual pair
  classifier and four-task loss.
- All 72 repository tests pass. No neural fitting, challenger ZIP or
  competition submission has occurred.

## Stage-2 unadapted dense baseline

The frozen Bami-v15 token checkpoint was loaded exactly, its NER head removed,
and mean-pooled backbone embeddings were evaluated without fitting. Over all
518 weak-link queries it achieved R@1/R@5/R@10 of 4.05/4.25/4.63%, below the
character baseline's 10.81/14.09/16.80%. Diagnosis retrieval was 0% at R@1 and
R@5; test diagnosis R@10 was also 0%. Drug R@1 was 21.43% overall.

This is a confirmatory negative result: an unchanged Vietnamese NER encoder
does not align Vietnamese mentions to English ontology titles. It strengthens,
rather than removes, the need for the preregistered mention/concept projection
training. The concept embeddings are cached by model+graph checksum; no
leaderboard submission or challenger artifact was produced. There are now 73
passing tests.

## Stage-3 alignment-only ablation

The frozen alignment-only variant selected epoch 20 and stopped at epoch 35.
It reached train R@1/R@5/R@10 of 30.28/52.82/61.03%, but collapsed to
2.78/5.56/8.33% on dev and 0.00/1.79/1.79% on test. Even the 28 test queries
whose concepts occurred in training achieved 0% R@1. The large train-to-dev
gap shows memorization of 426 pseudo links rather than ontology retrieval.

This variant fails both the lexical gate and the generalization requirement.
Under the registered failure policy, the graph-hard-negative variant is not
run on the same failed random-projection representation. H23 remains the
fallback; no ZIP or competition submission was created. There are now 75
passing tests. The next experiment must preserve pretrained geometry, create
clinical mention prototypes, and mine false candidates over the complete
ontology instead of relying only on in-batch negatives.

## Stage-4 train-only clinical prototypes

Replacing 287 seen ontology title embeddings with normalized means of their
train-only Vietnamese mentions required no fitted parameters. It lifted train
R@1 to 58.69%, but dev/test reached only 2.78/5.36%. Test R@5 improved from
the unadapted dense baseline's 5.36% to 8.93%, including three prototype-only
hits, but dev regressed from 5.56% R@1 and the overall test R@1 was unchanged.

The prototype gate therefore fails. It shows limited complementary diagnosis
signal but not a general retriever. The next retrieval baseline replaces the
NER encoder with a dedicated multilingual embedding model; sparse lexical
retrieval remains the fallback and graph reranking remains conditional.

## Stage-5 Qwen3 multilingual dense retrieval

The pinned `qwen3-embedding:0.6b` indexed all 69,991 canonical titles in
1,391 seconds and encoded all queries without fitting. Overall
R@1/R@5/R@10 is 10.23/26.45/35.91%. Dev reaches 8.33/22.22/25.00% and test
14.29/26.79/37.50%.

The strict R@1 promotion gate does not pass because dev R@1 remains below
lexical 11.11%. However, the candidate-pool result is materially positive:
test R@10 rises from lexical 21.43% to 37.50%, and diagnosis test R@1 reaches
12.77%. Drug R@1 falls relative to lexical. Under the frozen failure policy,
the next ablation is a parameter-free type specialist: Qwen for diagnoses and
lexical retrieval for drugs. Graph/reranking is now permitted only above that
stronger fused baseline.
