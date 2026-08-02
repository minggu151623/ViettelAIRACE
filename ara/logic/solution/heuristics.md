# Heuristics

## H01: Recognize standard checkpoint artifacts
- **Rationale**: Hugging Face `save_pretrained` normally writes `model.safetensors` or `pytorch_model.bin`, not the legacy `heads.pt`.
- **Provenance**: ai-suggested
- **Sensitivity**: low
- **Code ref**: [`airace/inference.py`]

## H02: Recover raw word boundaries at sliding-window edges
- **Rationale**: Token offsets at overflow boundaries can expose fragments such as `G` / `ãy`; expanding alphanumeric edges restores valid raw-word spans.
- **Provenance**: ai-suggested
- **Sensitivity**: medium
- **Code ref**: [`airace/train.py`]

## H03: Gate recall additions by two-model agreement
- **Rationale**: Raw learned union added more than 600 spans; requiring teacher confidence, student overlap, and no V6 overlap reduces this to 169.
- **Provenance**: ai-suggested
- **Sensitivity**: high
- **Code ref**: [`airace/ensemble.py`]

## H04: Make ZIP metadata deterministic
- **Rationale**: Fixed timestamps and permissions produce byte-identical archives from identical JSON files.
- **Provenance**: ai-suggested
- **Sensitivity**: low
- **Code ref**: [`airace/package_output.py`]

## H05: Promote numeric lab pairs only through existing compound results
- **Rationale**: Numeric adjacency alone produced treatment/vital-sign hazards.
  Requiring an existing result span to cover both a supported name and value
  bounds the rewrite to the previously audited 23 compound rows.
- **Provenance**: ai-suggested
- **Sensitivity**: medium
- **Code ref**: [`airace/evidence_rebuild.py`, `airace/lab_splitter.py`]

## H06: Make ontology review authoritative and family-consistent
- **Rationale**: Preserving old candidates after rejection defeats semantic
  review, while alphabetical selection can join unrelated ICD families. Select
  only reviewed/curated WHO codes and allow parent+child only within one family.
- **Provenance**: ai-suggested
- **Sensitivity**: high
- **Code ref**: [`airace/who_icd_rebuild.py`]

## H07: Separate categorical adjudication from copied confidence
- **Rationale**: H20's Qwen response copied proposal confidence. Use categorical
  KEEP/DROP only where its behavior is coherent, and route medication spans to
  exact supervised-model agreement plus deterministic boundary filters.
- **Provenance**: ai-suggested
- **Sensitivity**: high
- **Code ref**: [`airace/turn2_expanded_pair.py`]

## H08: Select calibration records without prediction access
- **Rationale**: Stratifying raw records by length and ranking them with a
  seeded hash prevents model errors or H20 coverage from influencing queue
  membership. Corpus and record fingerprints make later input drift visible.
- **Provenance**: ai-suggested
- **Sensitivity**: medium
- **Code ref**: [`airace/blind_eval.py`,
  `experiments/H21_blind_promotion_gate/calibration_manifest.json`]

## H09: Fail closed when stripping calibration sentinels
- **Rationale**: Synthetic unmatched rows are identifiable by impossible
  offsets and literal sentinel text, but a malformed real annotation must not
  be silently discarded by the same filter. Drop only explicit sentinels and
  abort on every other invalid row.
- **Provenance**: ai-suggested
- **Sensitivity**: low
- **Code ref**: [`airace/pseudo_reconstruct.py`,
  `tests/test_pseudo_reconstruct.py`]

## H10: Hedge ontology versions without replacing the known specific code
- **Rationale**: Blanket CM-to-WHO conversion discards information already
  supported by H22. For singleton same-family cases, `[parent, specific]`
  preserves that evidence while adding the organizer-supported WHO category;
  multi-family rows remain quarantined.
- **Provenance**: ai-suggested
- **Sensitivity**: high
- **Code ref**: [`airace/candidate_semantic.py`,
  `tests/test_candidate_semantic.py`]

## H11: Treat proposal disagreement as positive-unlabeled data
- **Rationale**: Organizer ground truth is absent, so a proposal missing from
  H23 may be a hidden true entity. Training every absent proposal as a clean
  negative would teach the new classifier to reproduce the current baseline
  and suppress exactly the recall needed for improvement.
- **Provenance**: ai-suggested
- **Sensitivity**: high
- **Code ref**: [`experiments/H24_ontology_graph_classifier/README.md`,
  `airace/ontology_retrieval.py`]

## H12: Use graph neighbours as hard alternatives, not automatic answers
- **Rationale**: Same-family ICD siblings and related RxNorm products are
  semantically close but often mutually incorrect. They are strong contrastive
  negatives for context learning; graph distance alone must not select the
  final candidate.
- **Provenance**: ai-suggested
- **Sensitivity**: high
- **Code ref**: [`airace/ontology_graph.py`, `airace/ontology_model.py`]

## H13: Route normalization by entity type before learning fusion weights
- **Rationale**: Cross-lingual dense retrieval recovers Vietnamese diagnoses,
  while exact lexical overlap remains substantially stronger for medication
  names. A fixed type router preserves both strengths and avoids calibrating
  incomparable scores on pseudo labels.
- **Provenance**: ai-suggested
- **Sensitivity**: medium
- **Code ref**: [`airace/ontology_fusion.py`,
  `experiments/H24_ontology_graph_classifier/type_specialist_protocol.yaml`]

## H14: Score only the final reranker token
- **Rationale**: Qwen relevance depends on the yes/no logits at the final
  position. Applying the language-model head only to the final hidden state is
  mathematically equivalent to materializing sequence-by-vocabulary logits and
  reduces memory enough for reproducible local ablations.
- **Provenance**: ai-suggested
- **Sensitivity**: low
- **Code ref**: [`airace/ontology_reranker.py`,
  `tests/test_ontology_reranker.py`]

## H15: Prevent confidence calibration before representation maturity
- **Rationale**: Cross-fold absolute confidence is meaningless when early
  stopping can retain epoch one. A minimum training duration lets the
  class-weighted encoder reach the late precision gains observed in H30.
- **Provenance**: ai-suggested
- **Sensitivity**: medium
- **Code ref**: [`airace/train.py`,
  `experiments/H34_minimum_epoch_recovery/protocol.yaml`]

## H16: Verify independent agreements against positive and hazard controls
- **Rationale**: Two proposal sources can share fused-boundary errors. Run
  frozen semantic and boundary decisions beside known-positive controls and
  registered hazards before promoting their novel intersection.
- **Provenance**: ai-suggested
- **Sensitivity**: high
- **Code ref**: [`airace/independent_agreement.py`,
  `airace/controlled_novel_verifier.py`]

## H17: Replace a verified contained boundary instead of unioning it
- **Rationale**: Adding a shorter core span beside its longer baseline span
  creates duplicate alternatives and likely precision loss. When support and
  type agree, replace the containing baseline span, inherit its assertions, and
  leave cross-type conflicts untouched.
- **Provenance**: ai-suggested
- **Sensitivity**: high
- **Code ref**: [`airace/verified_symptom_boundary.py`,
  `tests/test_verified_symptom_boundary.py`]

## H18: Freeze and hash every view before multi-view adjudication
- **Rationale**: A consensus experiment is not reproducible if a proposal bank
  silently changes between registration and inference. Hash file names and
  contents with explicit delimiters, fail before LLM review on any mismatch,
  and verify the final output and ZIP across two complete runs.
- **Provenance**: ai-suggested
- **Sensitivity**: low
- **Code ref**: [`airace/multiview_consensus.py`,
  `tests/test_multiview_consensus.py`]

## H19: Reuse spans across exact passages but relabel assertions per occurrence
- **Rationale**: Literal passage equality guarantees character-offset
  projection for a reviewed span/type, while historical, negated and family
  status can change with surrounding record context. Review the unique passage
  once, then show ±200 raw characters and collect assertions for every entity
  occurrence separately.
- **Provenance**: ai-suggested
- **Sensitivity**: high
- **Code ref**: [`airace/passage_annotation.py`,
  `airace/passage_annotation_app.py`, `tests/test_passage_annotation.py`]

## H20: Bootstrap passage clusters, not projected occurrences
- **Rationale**: Exact projection increases labeled coverage but copies the
  passage-level error source. Resample unique passage IDs inside the frozen
  high/middle/low strata, aggregate assertion variation within passage, and
  report occurrence-weighted estimates as descriptive only.
- **Provenance**: ai-suggested
- **Sensitivity**: high
- **Code ref**: [`airace/h41_cluster_gate.py`,
  `tests/test_h41_cluster_gate.py`]

## H21: Gate LLM review with longitudinal hazards
- **Rationale**: Two seeds can agree perfectly because they share the same
  prompt, context construction and model. Require reproduction of independently
  frozen prior contradictions before allowing a full-head semantic rewrite;
  delete the artifact when this temporal gate fails.
- **Provenance**: ai-suggested
- **Sensitivity**: high
- **Code ref**: [`airace/candidate_surgery.py`,
  `tests/test_candidate_surgery.py`]

## H22: Audit intervention concentration before claiming corpus breadth
- **Rationale**: Raw changed-row counts can overstate generalization when the
  same family or normalized mention repeats. Pair unique counts with inverse-
  Simpson effective counts and top-k shares, then freeze the semantic scope of
  an external result before its score is visible.
- **Provenance**: ai-suggested
- **Sensitivity**: medium
- **Code ref**: [`airace/exposure_concentration.py`,
  `experiments/H53_h44_exposure_concentration/protocol.yaml`]
