# Claims

## C01: Standard Hugging Face checkpoints were silently disabled
- **Statement**: Before the V15 repair, inference required `heads.pt`, so checkpoints saved as `model.safetensors` fell back to rules.
- **Status**: supported
- **Provenance**: ai-suggested
- **Falsification criteria**: Demonstrate a pre-repair execution path that loaded `model.safetensors` without `heads.pt`.
- **Proof**: [`airace/inference.py`, `tests/test_core.py`]
- **Dependencies**: []
- **Tags**: checkpoint, inference, defect

## C02: Class weighting improves the current biased local proxy
- **Statement**: Inverse-square-root BIO class weighting raises strict span/type F1 from 0.690476 to 0.867470 on the 9-record reviewed holdout.
- **Status**: supported
- **Provenance**: ai-suggested
- **Falsification criteria**: Reproduction with the locked data, seed, and checkpoint fails to obtain the reported metrics.
- **Proof**: [`models/bami-airace-v15-weighted/training_report.json`, `experiments/H_weighted_token_model/analysis.md`]
- **Dependencies**: [C01]
- **Tags**: BamiBERT, class-imbalance, local-proxy

## C03: High-confidence teacher–student consensus may improve hidden recall
- **Statement**: Adding only non-overlapping spans agreed by an original medical teacher and supervised student is safer than raw model union.
- **Status**: refuted
- **Provenance**: ai-suggested
- **Falsification criteria**: V16 scores at or below the externally verified V6 score of 1.7280, or manual review shows unacceptable false positives.
- **Proof**: [`reports/v16_teacher_student.json`, external score `1.6868` versus V6 `1.7280`]
- **Dependencies**: [C01, C02]
- **Tags**: ensemble, consensus, leaderboard

## C04: Official example offsets are consistent with CRLF coordinates
- **Statement**: The published example offsets can be reconstructed exactly by
  inserting CRLF line breaks before the numbered items, suggesting that gold
  positions may use CRLF coordinates while distributed inputs use LF.
- **Status**: supported externally
- **Provenance**: ai-suggested
- **Falsification criteria**: The isolated CRLF position-only artifact scores
  no better than the raw-coordinate V6 baseline, or the official evaluator is
  shown to normalize positions before matching.
- **Proof**: [`experiments/H_crlf_coordinate_reconstruction/protocol.md`,
  `experiments/H_crlf_coordinate_reconstruction/analysis.md`,
  `reports/v17_crlf_positions.json`, `input.zip` archive metadata,
  `research-log.md` H7 external result]
- **Dependencies**: []
- **Tags**: coordinates, CRLF, black-box-ablation

## C05: Numeric-first RxCUI fallback produces semantic contradictions
- **Statement**: V6 candidate resolution selects some active but unsupported
  combination, strength, form, or route concepts because numeric RxCUI order
  precedes semantic evidence.
- **Status**: supported
- **Provenance**: ai-suggested
- **Falsification criteria**: Reproduction shows the flagged concepts match all
  ingredients, strength, form, and route explicitly present in their mentions.
- **Proof**: [`experiments/H_rxnorm_active_audit/results.json`,
  `experiments/H_rxnorm_active_audit/analysis.md`, `airace/candidates.py`]
- **Dependencies**: []
- **Tags**: RxNorm, candidates, resolver, semantic-ranking

## C06: Diagnosis gold can contain parent and specific ICD candidates
- **Statement**: The organizer's pre-round overview demonstrates more than one
  ICD candidate for a single diagnosis, including a parent and a more-specific
  code.
- **Status**: supported for high-level policy
- **Provenance**: ai-suggested
- **Falsification criteria**: The original organizer overview is shown to be
  unauthentic, or the round evaluator explicitly excludes diagnosis candidates.
- **Proof**: [`literature/organizer_overview_example.md`]
- **Dependencies**: []
- **Tags**: ICD-10, candidates, organizer-example

## C07: Catastrophic semantic recall does not explain V6 text credit
- **Statement**: V6 covers nearly all explicit target-bearing fields in the
  semi-structured inputs, so `0.0398%` official text credit is more consistent
  with matching/coordinate failure than globally irrelevant extraction.
- **Status**: supported as a field-level diagnostic
- **Provenance**: ai-suggested
- **Falsification criteria**: Entity-level independent annotation shows that
  overlapping V6 mentions systematically have wrong boundaries or types
  despite the field coverage.
- **Proof**: [`experiments/H_structured_field_coverage/analysis.md`]
- **Dependencies**: [C04]
- **Tags**: coverage, matching, coordinates, diagnostic

## C08: i2b2 is a useful boundary prior but not direct BTC gold
- **Statement**: BTC's schema strongly corresponds to an adapted i2b2
  problem/test/treatment task, while documented assertion and type-split
  differences make mechanical label conversion invalid.
- **Status**: supported as a policy prior
- **Provenance**: ai-suggested
- **Falsification criteria**: BTC documentation or independent annotation
  demonstrates boundary behavior systematically incompatible with i2b2 rules.
- **Proof**: [`literature/i2b2_policy_mapping.md`]
- **Dependencies**: []
- **Tags**: i2b2, annotation-policy, boundaries, assertions

## C09: Primary i2b2 guidelines provide actionable span and scope rules
- **Statement**: The official i2b2/VA guidelines support complete NP/AP boundaries,
  structured PP/list handling, separate occurrences, and Possible-over-Absent
  precedence as an independent policy prior.
- **Status**: supported as an external policy prior
- **Provenance**: ai-suggested
- **Falsification criteria**: The cited guideline text does not contain these rules,
  or independent BTC evidence systematically contradicts them.
- **Proof**: [`literature/i2b2_guideline_extract.md`]
- **Dependencies**: [C08]
- **Tags**: i2b2, boundaries, scope, assertions

## C10: Compound-symptom segmentation is phrase-specific
- **Statement**: The organizer sample contradicts both global split-all and
  merge-all rules for adjacent symptom phrases, so such transformations require
  phrase-level evidence.
- **Status**: supported by official sample
- **Provenance**: ai-suggested
- **Falsification criteria**: The sample is corrected by the organizer, or a
  published rule explains both boundaries with a deterministic general rule.
- **Proof**: [`literature/official_sample_boundary_policy.md`]
- **Dependencies**: [C09]
- **Tags**: boundaries, symptoms, organizer-sample

## C11: Public records share a translation/restructuring template
- **Statement**: The 100 public inputs are strongly consistent with a common
  template-based translation or restructuring process rather than independently
  authored Vietnamese clinical notes.
- **Status**: supported for templating; named source unproven
- **Provenance**: ai-suggested
- **Falsification criteria**: Independent provenance shows the records were
  natively authored under the same template, or repeated-heading and mixed-
  language counts are not reproducible.
- **Proof**: [`experiments/H_source_generation/analysis.md`]
- **Dependencies**: [C08]
- **Tags**: provenance, templating, bilingual, sections

## C12: Named i2b2 source provenance is not established
- **Statement**: BTC and i2b2 share strong task-family/schema resemblance, but
  there is no record-level evidence that the BTC inputs derive from i2b2 2010.
- **Status**: supported as a scope limitation
- **Provenance**: ai-suggested
- **Falsification criteria**: An exact licensed source-to-BTC record alignment
  is recovered with reproducible text and annotation correspondence.
- **Proof**: [`literature/source_corpus_provenance_assessment.md`]
- **Dependencies**: [C08, C11]
- **Tags**: provenance, i2b2, data-access, scope

## C13: Unsupported candidates are worse than abstention
- **Statement**: Candidate codes without semantic support can erase candidate
  credit, while leaving candidate lists empty preserves structural empty-set
  credit.
- **Status**: supported by internal and independent black-box ablations
- **Provenance**: ai-suggested
- **Falsification criteria**: Auditable controlled submissions show unsupported
  candidate addition consistently improves candidate score over identical
  entities with empty candidate lists.
- **Proof**: [`literature/forum_peer_blackbox_evidence_2026-07-27.md`,
  `research-state.yaml`]
- **Dependencies**: []
- **Tags**: candidates, abstention, jaccard, black-box

## C14: Family reporter is not family experiencer
- **Statement**: `isFamily` should mark a condition belonging to a relative, not
  a relative reporting the patient's condition; V6 violates this distinction
  in 18 of its 19 family-labeled contexts.
- **Status**: strongly supported semantically; external score pending
- **Provenance**: ai-suggested
- **Falsification criteria**: Organizer policy explicitly defines family
  reporter as `isFamily`, or an isolated removal consistently reduces assertion
  score under reproducible submissions.
- **Proof**: [`experiments/H_assertion_policy_audit/analysis.md`,
  `literature/i2b2_guideline_extract.md`]
- **Dependencies**: [C09]
- **Tags**: assertions, family, experiencer, scope

## C15: V6 merges laboratory names into result spans
- **Statement**: V6 systematically emits compound numeric laboratory rows as
  result concepts rather than independent test-name and value/unit concepts.
- **Status**: structurally supported; external score untested
- **Provenance**: ai-suggested
- **Falsification criteria**: Independent annotation shows that BTC expects
  compound `name + value` result spans for numeric laboratory rows.
- **Proof**: [`experiments/H_test_result_boundary_audit/analysis.md`,
  `literature/official_forum_policy_2026-07-27.md`]
- **Dependencies**: []
- **Tags**: tests, results, boundaries, typing

## C16: V18 implements a bounded evidence bundle without proving external gain
- **Statement**: V18 deterministically applies only the preregistered lab,
  assertion, RxNorm, and optional CRLF interventions to the externally best V6
  source, while passing all local schema/offset checks.
- **Status**: supported internally; external score untested
- **Provenance**: ai-executed
- **Falsification criteria**: Reproduction changes fields outside the declared
  intervention surface, fails any of the 100 output validations, or produces a
  different archive hash from identical inputs.
- **Proof**: [`reports/v18_evidence_lf.json`,
  `reports/v18_evidence_crlf.json`, `reports/v18_delta_audit.json`,
  `output_v18_evidence_crlf.zip`]
- **Dependencies**: [C04, C05, C14, C15]
- **Tags**: integration, determinism, validation, external-pending

## C17: The V18 semantic bundle regresses against isolated H7
- **Statement**: Combining lab splitting, assertion refresh, and RxNorm repair
  under CRLF lowers the hidden score relative to CRLF positions alone.
- **Status**: supported externally; causal component unisolated
- **Provenance**: user
- **Falsification criteria**: A corrected submission identity or evaluator
  result shows V18 at least equal to H7, or an isolated semantic axis
  reproduces the full gain without the bundle regression.
- **Proof**: [`research-log.md` V18 external regression,
  `reports/v18_evidence_crlf.json`]
- **Dependencies**: [C04, C16]
- **Tags**: regression, assertions, laboratory, black-box

## C18: Reviewer-authoritative WHO selection repairs H18 structural defects
- **Statement**: Diagnosis candidate reconstruction must permit reviewer
  rejection of old codes and forbid parent/child pairs across different WHO
  three-character families; H18 violated both requirements and H19 enforces them.
- **Status**: supported internally; leaderboard effect untested
- **Provenance**: ai-suggested
- **Falsification criteria**: H19 reproduction retains a reviewer-rejected old
  code, emits a non-WHO code, changes a frozen non-candidate field, or fails
  validation.
- **Proof**: [`experiments/H19_turn2_who_precision/selection.json`,
  `experiments/H19_turn2_who_precision/merge_report.json`,
  `turn2/output_v5_who_precision.zip`]
- **Dependencies**: [C06, C13]
- **Tags**: WHO-ICD, candidates, precision, deterministic

## C19: Qwen review confidence is uncalibrated in H20
- **Statement**: The numeric confidence emitted in the frozen H20 review copies
  proposal-model confidence and cannot be interpreted as Qwen's probability of
  a correct KEEP/DROP decision.
- **Status**: supported by frozen review output
- **Provenance**: ai-suggested
- **Falsification criteria**: Repeated schema-constrained review with hidden
  proposal confidences yields the same numeric values and they calibrate against
  independently annotated spans.
- **Proof**: [`experiments/H20_turn2_expanded_pair/review.json`]
- **Dependencies**: []
- **Tags**: calibration, Qwen, confidence, adjudication

## C20: H20 is an externally supported architecture-scale recall candidate
- **Statement**: H20 adds 500 disjoint exact two-model entities while preserving
  all 1,950 H19 entities exactly and satisfying deterministic validation; this
  is a materially different intervention from H17's 66-row micro-layer.
- **Status**: supported externally as a combined intervention
- **Provenance**: ai-suggested
- **Falsification criteria**: Submission identity is shown not to match the
  registered artifact, or a reproducible evaluation contradicts the reported
  29.8409 result and its component metrics.
- **Proof**: [`experiments/H20_turn2_expanded_pair/merge_report.json`,
  `experiments/H20_turn2_expanded_pair/analysis.md`,
  `turn2/output_v6_expanded_pair.zip`, `research-log.md`]
- **Dependencies**: [C18, C19]
- **Tags**: ensemble, recall, NER, external-pending

## C21: H21 fails closed before hidden evaluation
- **Statement**: A challenger cannot be promoted by H21 when annotations are
  missing or invalid, when evaluated on the development split, or when it
  violates the preregistered bootstrap, strict-F1, component-floor, and
  record-level non-regression checks.
- **Status**: supported internally; organizer-policy transfer untested
- **Provenance**: ai-suggested
- **Falsification criteria**: Any incomplete or development-only fixture emits
  `PROMOTE`, manifest regeneration changes selected records under identical
  input, modified input passes fingerprint validation, or a gate condition can
  fail while holdout still emits `PROMOTE`.
- **Proof**: [`airace/blind_eval.py`, `tests/test_blind_eval.py`,
  `experiments/H21_blind_promotion_gate/reports/smoke_incomplete.json`]
- **Dependencies**: [C20]
- **Tags**: blind-validation, bootstrap, promotion, safety

## C22: H22 is a calibrated proxy challenger, not recovered gold
- **Statement**: The collaborator fixture separates into 3,168 raw-aligned
  pseudo-labels and 940 synthetic out-of-range rows; removing every synthetic
  row yields a valid independent challenger whose transfer to organizer policy
  requires external confirmation.
- **Status**: supported externally as a transfer intervention
- **Provenance**: ai-suggested
- **Falsification criteria**: Any retained H22 row fails raw-offset validation,
  a calibration dummy survives packaging, identical builds differ, or the
  submitted artifact fails to improve over H20 under the organizer evaluator.
- **Proof**: [`experiments/H22_calibrated_pseudo_reconstruction/build_report.json`,
  `experiments/H22_calibrated_pseudo_reconstruction/proxy_comparison.json`,
  `turn2/output_v7_pseudo_reconstruction.zip`]
- **Dependencies**: [C20, C21]
- **Tags**: pseudo-labels, calibration, reconstruction, external-pending

## C23: The H22 proxy is directionally useful but not score-calibrated
- **Statement**: The pseudo-label proxy can identify a productive
  architecture-scale replacement, but its in-sample score cannot forecast the
  organizer score or safely tune small variants.
- **Status**: supported externally
- **Provenance**: ai-suggested
- **Falsification criteria**: Multiple preregistered challengers show that
  proxy score differences accurately predict both leaderboard ranking and
  absolute score within a small error bound.
- **Proof**: [`experiments/H22_calibrated_pseudo_reconstruction/proxy_comparison.json`,
  `experiments/H22_calibrated_pseudo_reconstruction/external_result.json`]
- **Dependencies**: [C22]
- **Tags**: proxy, calibration, leaderboard, scope

## C24: Same-family parent addition is a bounded ontology hedge
- **Statement**: For an ICD-10-CM-specific singleton diagnosis code absent from
  WHO 2019, adding—without replacing—the valid three-character WHO parent
  hedges ontology-version uncertainty while preserving the externally useful
  specific code and all extraction fields.
- **Status**: supported externally with small effect; axis closed
- **Provenance**: ai-suggested
- **Falsification criteria**: A changed row crosses disease families, exceeds
  two candidates, changes a frozen field, or the candidate-only external test
  lowers candidate Jaccard relative to H22.
- **Proof**: [`airace/candidate_semantic.py`,
  `experiments/H23_candidate_only_semantic/build_report.json`,
  `experiments/H23_candidate_only_semantic/external_result.json`,
  `turn2/output_v8_candidate_semantic.zip`]
- **Dependencies**: [C06, C18, C22]
- **Tags**: ICD-10, ICD-10-CM, parent, candidates, external-pending

## C25: Parent-list expansion is not a breakthrough path
- **Statement**: Candidate-only same-family WHO parent expansion is valid but
  too small to bridge the remaining leaderboard gap; model-core changes must
  affect contextual extraction and normalization together.
- **Status**: supported by one controlled external ablation
- **Provenance**: ai-suggested
- **Falsification criteria**: A separately preregistered parent-list policy
  produces a multi-point gain while preserving WER and assertion metrics.
- **Proof**: [`experiments/H23_candidate_only_semantic/external_result.json`]
- **Dependencies**: [C24]
- **Tags**: candidates, saturation, pivot, black-box

## C26: Vietnamese diagnosis normalization has large semantic headroom
- **Statement**: Character-only retrieval over the exact WHO/RxNorm graph is
  inadequate for Vietnamese diagnosis mentions, so a cross-lingual contextual
  encoder with ontology structure has measurable headroom over lexical lookup.
- **Status**: testing; lexical baseline supported, dense/graph gain pending
- **Provenance**: ai-suggested
- **Falsification criteria**: An alias-held-out dense+graph model fails to beat
  lexical Recall@1 by 5 points and Recall@5 by 8 points under the frozen H24
  protocol, or the pseudo-link labels prove unusably inconsistent.
- **Proof**: [`experiments/H24_ontology_graph_classifier/lexical_baseline.json`,
  `experiments/H24_ontology_graph_classifier/graph_manifest.json`]
- **Dependencies**: [C23, C25]
- **Tags**: ontology, graph, retrieval, Vietnamese, diagnosis

## C27: Retrieval-pretrained multilingual geometry beats weak projection fitting
- **Statement**: On the frozen 69,991-node ontology and alias-group split,
  Qwen3 Embedding expands held-out top-k recall while alignment heads trained
  from 426 H23-derived rows collapse out of sample.
- **Status**: supported internally; organizer transfer untested
- **Provenance**: ai-suggested
- **Falsification criteria**: A repeated frozen-split run makes the learned
  alignment model match Qwen on dev/test R@5, or an independent organizer-like
  corpus reverses their ranking.
- **Proof**: [`experiments/H24_ontology_graph_classifier/alignment_only/report.json`,
  `experiments/H24_ontology_graph_classifier/qwen_multilingual/report.json`]
- **Dependencies**: [C26]
- **Tags**: multilingual, retrieval, alignment, weak-labels

## C28: Entity-type routing is the strongest H24 linker
- **Statement**: A zero-parameter router using multilingual dense retrieval
  for diagnoses and character TF-IDF for drugs improves both dev and test
  Recall@1 and Recall@5 over the frozen lexical baseline.
- **Status**: supported internally; promoted as candidate generator only
- **Provenance**: ai-suggested
- **Falsification criteria**: Rebuilding from pinned inputs changes the
  rankings, or an independent labeled set shows either specialist is weaker
  than its alternative for the routed type.
- **Proof**: [`experiments/H24_ontology_graph_classifier/type_specialist/report.json`,
  `experiments/H24_ontology_graph_classifier/type_specialist_protocol.yaml`]
- **Dependencies**: [C27]
- **Tags**: routing, diagnosis, drug, dense, lexical

## C29: Generic semantic reranking does not dominate specialist retrieval
- **Statement**: The pinned Qwen3 Reranker, with or without direct ontology
  relation text, fails to improve aggregate test Recall@1 or Recall@5 over the
  fixed type-specialist router.
- **Status**: refuted as a promotion path on H24
- **Provenance**: ai-suggested
- **Falsification criteria**: A preregistered context representation or graph
  encoding clears the router gate on an independent record-held-out set.
- **Proof**: [`experiments/H24_ontology_graph_classifier/reranker/report.json`,
  `experiments/H24_ontology_graph_classifier/reranker_protocol.yaml`]
- **Dependencies**: [C28]
- **Tags**: reranker, graph, ablation, negative-result

## C30: H23 weak links are insufficient for deeper linker fitting
- **Statement**: A train-only classifier over the union candidate pool adds
  only one test Recall@5 hit and no Recall@1 gain; graph features add no dev
  gain, so further fitting on the same 518 pseudo links is not justified.
- **Status**: supported internally; scope limited to the current feature family
- **Provenance**: ai-suggested
- **Falsification criteria**: A preregistered model using only the same weak
  rows clears the fixed router's dev R@1 and R@5 gates without leakage.
- **Proof**: [`experiments/H24_ontology_graph_classifier/feature_classifier/report.json`,
  `experiments/H24_ontology_graph_classifier/feature_classifier_protocol.yaml`]
- **Dependencies**: [C28, C29]
- **Tags**: weak-labels, classifier, graph, saturation, pivot

## C31: Weak-label token confidence is useful only after held-out calibration
- **Statement**: The H30 token model learns transferable clinical spans, but
  only its record-held-out high-confidence subset reaches useful precision;
  the uncalibrated model is not safe as a direct H23 replacement.
- **Status**: supported internally; organizer transfer untested
- **Provenance**: ai-suggested
- **Falsification criteria**: Reproduction fails to obtain at least 80% strict
  precision on both frozen H31 splits, or unthresholded H30 proves equally
  precise on independent labels.
- **Proof**: [`experiments/H30_weak_label_adaptation/results/report.json`,
  `experiments/H31_confidence_calibration/results/report.json`]
- **Dependencies**: [C30]
- **Tags**: weak-labels, token-classifier, confidence, calibration

## C32: Minimum training duration is required for cross-fold confidence
- **Statement**: Under the current class-weighted token schedule, early
  stopping before epoch five can retain an immature checkpoint that emits no
  high-confidence spans; enforcing five minimum epochs repairs the collapse.
- **Status**: supported internally
- **Provenance**: ai-suggested
- **Falsification criteria**: The frozen failed fold remains empty after the
  registered minimum-epoch rerun, or the reported aggregate repair cannot be
  reproduced.
- **Proof**: [`experiments/H33_per_fold_calibration/results/report.json`,
  `experiments/H34_minimum_epoch_recovery/results/report.json`, `airace/train.py`]
- **Dependencies**: [C31]
- **Tags**: early-stopping, crossfit, calibration, training

## C33: Independent agreement plus controlled verification isolates useful novel spans
- **Statement**: Exact agreement between the cross-fit token model and an
  independent source, followed by two frozen semantic/boundary prompts, can
  reject registered fused-token hazards while retaining at least 85% of known
  positive controls.
- **Status**: supported internally; organizer transfer untested
- **Provenance**: ai-suggested
- **Falsification criteria**: Frozen H36 reproduction retains either registered
  hazard, drops more than 15% of controls, or falls below 80% prompt agreement.
- **Proof**: [`experiments/H35_independent_agreement_audit/results/report.json`,
  `experiments/H36_controlled_novel_verifier/results/report.json`]
- **Dependencies**: [C31, C32]
- **Tags**: agreement, verifier, controls, NER

## C34: Verified symptom proposals expose H23 boundary inflation
- **Statement**: Most H36-accepted symptoms absent by exact H23 matching are
  shorter core spans inside longer H23 symptom mentions rather than entirely
  new mentions; a bounded replacement can isolate this policy difference
  without changing candidates.
- **Status**: supported externally but effect is negligible
- **Provenance**: ai-suggested
- **Falsification criteria**: H37 changes a candidate or unaffected entity,
  applies a cross-type conflict, or fails deterministic validation. The external
  effect was positive but too small to justify further micro-queues.
- **Proof**: [`experiments/H37_verified_symptom_boundary/results/report.json`,
  `turn2/output_v9_verified_symptoms.zip`]
- **Dependencies**: [C33]
- **Tags**: boundary, symptoms, replacement, deterministic

## C35: Multi-view exact consensus scales proposal coverage but not independence
- **Statement**: Requiring exact agreement among at least three of five frozen
  proposal views, followed by dual semantic/boundary verification, can scale a
  controlled novel queue beyond 150 rows; agreement does not eliminate errors
  shared through weak-label ancestry.
- **Status**: supported externally but insufficient as a breakthrough path
- **Provenance**: ai-suggested
- **Falsification criteria**: A frozen rerun changes accepted rows or bytes,
  retains a registered hazard, or loses more than 15% of positive controls. The
  external result was positive but only +0.3093, closing threshold expansion.
- **Proof**: [`experiments/H38_multiview_consensus/results/report.json`,
  `experiments/H38_multiview_consensus/results/determinism.json`,
  `experiments/H38_multiview_consensus/analysis.md`]
- **Dependencies**: [C33, C34]
- **Tags**: ensemble, agreement, controls, correlated-errors, NER

## C36: Source dependence must be modeled before weak-label stacking
- **Statement**: A latent label model with type-specific source confusion and
  explicit proposal-family dependence can outperform equal-weight majority
  voting under correlated noise and leave-one-family-out evaluation.
- **Status**: refuted on real leave-one-family-out cells; synthetic mechanism supported
- **Provenance**: ai-suggested
- **Falsification criteria**: H39 fails to beat majority F1 by five points on
  the locked correlated-noise benchmark, or fails a type-specific leave-one-
  family-out log-loss gate.
- **Proof**: [`experiments/H39_dependency_aware_label_model/protocol.yaml`,
  `experiments/H39_dependency_aware_label_model/results/early_gates.json`]
- **Dependencies**: [C35]
- **Tags**: weak-supervision, label-model, dependencies, stacker

## C37: Exact repetition is a label multiplier, not a label source
- **Statement**: Exact repeated Turn-2 passages can multiply independently
  reviewed span/type labels across records, but automatic modal model evidence
  is not stable enough to determine the annotation policy by itself.
- **Status**: first clause operationalized; automatic-policy clause supported internally
- **Provenance**: ai-suggested
- **Falsification criteria**: H40 reproduces at least 95% leave-one-occurrence-
  out stability under the frozen gates, or H41 projection fails exact offset
  round-trip on any selected occurrence.
- **Proof**: [`experiments/H40_repeated_passage_consistency/results/early_gates.json`,
  `experiments/H41_repeated_passage_blind_annotation/results/queue_audit.json`]
- **Dependencies**: [C35, C36]
- **Tags**: repeated-passages, annotation, independence, projection

## C38: Repeated occurrences are not independent promotion units
- **Statement**: H41 must resample unique passages within its frozen strata;
  treating exact repeated occurrences as independent bootstrap observations
  materially inflates false promotion under plausible within-passage error
  correlation.
- **Status**: supported by preregistered simulation; real-label calibration pending
- **Provenance**: ai-suggested
- **Falsification criteria**: The frozen H42 simulation fails either registered
  reduction gate, or an independent derivation shows occurrence resampling
  controls the nominal error despite shared passage effects.
- **Proof**: [`experiments/H42_h41_cluster_gate/protocol.yaml`,
  `experiments/H42_h41_cluster_gate/results/null_simulation.json`,
  `airace/h41_cluster_gate.py`]
- **Dependencies**: [C37]
- **Tags**: bootstrap, clustered-data, repeated-passages, promotion-gate

## C39: Same-run LLM agreement does not establish candidate-review stability
- **Statement**: Agreement between deterministic seeds under one prompt batch
  is insufficient to authorize ontology pruning when decisions fail to
  reproduce frozen known-title contradictions from an earlier review.
- **Status**: supported internally by H43
- **Provenance**: ai-suggested
- **Falsification criteria**: A preregistered repeat review reproduces at least
  80% of independent frozen hazard uses while preserving positive controls.
- **Proof**: [`experiments/H43_candidate_contradiction_surgery/protocol.yaml`,
  `experiments/H43_candidate_contradiction_surgery/results/build_report.json`]
- **Dependencies**: [C13]
- **Tags**: LLM-review, calibration, temporal-stability, candidates

## C40: H23's mixed-hierarchy policy may generalize corpus-wide
- **Statement**: Preserving each specific diagnosis code while adding its valid
  WHO three-character family across all eligible H38 singletons may improve
  candidate Jaccard without changing WER or assertion score.
- **Status**: locally validated submission candidate; external result pending
- **Provenance**: ai-suggested
- **Falsification criteria**: H44 changes any non-candidate field, fails
  deterministic validation, or externally lowers candidate Jaccard relative to
  H38 while WER/assertions remain invariant.
- **Proof**: [`experiments/H44_full_who_family_hedge/protocol.yaml`,
  `experiments/H44_full_who_family_hedge/results/build_report.json`,
  `experiments/H44_full_who_family_hedge/external_decision_tree.yaml`,
  `turn2/output_v12_full_who_family_hedge.zip`]
- **Dependencies**: [C24, C25, C39]
- **Tags**: WHO-ICD, hierarchy, parent-specific, submission-candidate

## C48: H44's locked strong gate represents material, not universal, transfer
- **Statement**: H44's 611 interventions are disjoint from H23's 144, and a
  +0.50 candidate-Jaccard result would retain about 34.25% of H23's
  exposure-normalized per-row yield rather than prove universal mixed-hierarchy
  prevalence.
- **Status**: lineage and arithmetic supported; external transfer pending
- **Provenance**: ai-suggested
- **Falsification criteria**: Stable record/position/specific-code identity
  reveals overlap between H23 and H44, or the frozen row counts and H23 external
  candidate delta do not reproduce the registered transfer ratios.
- **Proof**: [`experiments/H52_h44_transfer_calibration/protocol.yaml`,
  `experiments/H52_h44_transfer_calibration/results/transfer.json`,
  `airace/h44_transfer.py`,
  `experiments/H44_full_who_family_hedge/external_decision_tree.yaml`]
- **Dependencies**: [C40]
- **Tags**: exposure-calibration, lineage, WHO-ICD, pre-result-interpretation

## C49: H44 has broad family exposure but limited effective lexical breadth
- **Statement**: H44's 611 interventions span enough distinct and effectively
  weighted WHO parent families to support a family-breadth interpretation, but
  repeated mention-specific units fail the preregistered lexical-breadth gate.
- **Status**: supported by preregistered pre-result concentration audit
- **Provenance**: ai-suggested
- **Falsification criteria**: Reproduction on the frozen H44 change report does
  not yield 148 families, effective family count 47.478189, 286 strictly
  normalized lexical units and effective lexical count 89.762202, or the H44
  artifact hash differs from the registered value.
- **Proof**: [`experiments/H53_h44_exposure_concentration/protocol.yaml`,
  `experiments/H53_h44_exposure_concentration/results/concentration.json`,
  `airace/exposure_concentration.py`,
  `experiments/H44_full_who_family_hedge/external_decision_tree.yaml`]
- **Dependencies**: [C40, C48]
- **Tags**: concentration, inverse-Simpson, WHO-ICD, lexical-diversity,
  pre-result-interpretation

## C50: H44 primarily tests cross-family extrapolation beyond H23
- **Statement**: Most H44 interventions belong to WHO parent families absent
  from H23, so H44's aggregate external result primarily measures cross-family
  extrapolation rather than within-family extension of H23.
- **Status**: supported by preregistered pre-result decomposition
- **Provenance**: ai-suggested
- **Falsification criteria**: Frozen reports fail to reproduce 461/611 rows and
  120/148 families in the H23-novel stratum, the strata fail to cover all H44
  rows, or the H44 artifact hash differs from its registered value.
- **Proof**: [`experiments/H54_h44_family_novelty_decomposition/protocol.yaml`,
  `experiments/H54_h44_family_novelty_decomposition/results/decomposition.json`,
  `airace/family_novelty.py`,
  `experiments/H44_full_who_family_hedge/external_decision_tree.yaml`]
- **Dependencies**: [C48, C49]
- **Tags**: extrapolation, family-novelty, WHO-ICD,
  pre-result-interpretation

## C51: H44 result ingestion is deterministic and fail-closed
- **Statement**: Given the frozen H44 tree, artifact and four finite metrics,
  the H55 recorder verifies identity and candidate-only invariants, selects one
  frozen branch deterministically, and writes no result on validation failure.
- **Status**: supported by synthetic software tests; real result pending
- **Provenance**: ai-suggested
- **Falsification criteria**: Any registered anomaly creates an output file or
  receives an attributable branch, any registered valid fixture maps to the
  wrong decision, repeat readiness reports differ, or a real accepted result
  is not bound to the submitted ZIP and decision-tree hashes.
- **Proof**: [`experiments/H55_h44_external_result_recorder/protocol.yaml`,
  `experiments/H55_h44_external_result_recorder/results/readiness.json`,
  `airace/h44_result_recorder.py`, `tests/test_h44_result_recorder.py`]
- **Dependencies**: [C48, C49, C50]
- **Tags**: result-integrity, fail-closed, preregistration, software-validation

## C41: Retrieval depth without cardinality calibration reduces candidate Jaccard
- **Statement**: H24's ranked ontology candidates cannot be converted into a
  better set prediction by selecting a fixed global or entity-type prefix size
  on the frozen weak-link development split.
- **Status**: supported internally; organizer transfer untested
- **Provenance**: ai-suggested
- **Falsification criteria**: A separately frozen, alias-disjoint evaluation
  selects a prefix above one on development and improves test macro-Jaccard by
  at least 0.02 with a positive paired-bootstrap lower bound.
- **Proof**: [`experiments/H45_jaccard_cardinality_audit/protocol.yaml`,
  `experiments/H45_jaccard_cardinality_audit/results/report.json`,
  `airace/candidate_set_utility.py`]
- **Dependencies**: [C40]
- **Tags**: Jaccard, set-valued-prediction, cardinality, calibration, candidates

## C42: Weak-link score shape is insufficient for safe row-level cardinality
- **Statement**: Frozen Qwen cosine score shape may contain diagnosis
  cardinality information, but the current alias-disjoint weak development set
  cannot calibrate a stable adaptive candidate-set policy.
- **Status**: weakened signal; rejected before test
- **Provenance**: ai-suggested
- **Falsification criteria**: On independently labeled diagnosis mentions, a
  protocol-frozen score-shape model improves dev Jaccard by at least 0.02 with
  a positive paired-bootstrap lower bound and mean selected k at most 3.
- **Proof**: [`experiments/H46_score_shape_cardinality/protocol.yaml`,
  `experiments/H46_score_shape_cardinality/results/report.json`,
  `airace/score_shape_cardinality.py`]
- **Dependencies**: [C41]
- **Tags**: score-margin, Jaccard, calibration, weak-labels, early-gate

## C43: Proposal-derived assertion harm recurs but has low observed leverage
- **Statement**: Assertions on H37/H38 novel entities are associated with
  repeated external assertion regression, but the observed weighted component
  loss is too small to justify blanket abstention as a reset-slot mechanism.
- **Status**: supported as a low-leverage internal/external ancestry audit
- **Provenance**: ai-suggested
- **Falsification criteria**: A preregistered isolated assertion-only external
  test recovers at least 0.10 total score points, or independent H41 labels show
  a high-precision subgroup with equivalent expected leverage.
- **Proof**: [`experiments/H47_novel_span_assertion_leverage/protocol.yaml`,
  `experiments/H47_novel_span_assertion_leverage/results/report.json`,
  `airace/assertion_leverage.py`]
- **Dependencies**: [C34, C35]
- **Tags**: assertions, negative-transfer, ancestry, leverage, abstention

## C44: The frozen H41 holdout is a high-effect gate, not an equivalence test
- **Statement**: Under Normal passage deltas, H41's 15 independent holdout
  passages control false promotion near 5% but lack 80% power for a
  standardized effect of 0.5; non-promotion cannot establish equivalence or
  absence of a moderate gain.
- **Status**: revised; underpower supported, universal Type-I wording narrowed
- **Provenance**: ai-suggested
- **Falsification criteria**: A preregistered reproducible power analysis of
  the same frozen gate gives at least 80% power at `d=0.5`, or an exact
  derivation shows the implemented simulation underestimates its sensitivity.
- **Proof**: [`experiments/H48_h41_power_curve/protocol.yaml`,
  `experiments/H48_h41_power_curve/results/power.json`,
  `airace/h41_power.py`,
  `experiments/H49_h41_power_robustness/results/power_envelope.json`]
- **Dependencies**: [C38]
- **Tags**: statistical-power, bootstrap, repeated-passages, equivalence

## C45: H41's percentile gate is distribution-sensitive at small sample sizes
- **Statement**: At 15 passages, the stratified percentile-bootstrap lower
  bound does not maintain a universal near-5% false-promotion rate across
  mean-zero, unit-variance discrete, heavy-tailed and skewed delta families;
  Normal-only power also understates the robust sample requirement.
- **Status**: supported by preregistered distributional simulation
- **Provenance**: ai-suggested
- **Falsification criteria**: A preregistered exact or Monte Carlo audit of the
  implemented gate shows Type-I within 0.02–0.08 for every frozen family and
  at least 80% power at `d=0.5` for 30 passages in every family.
- **Proof**: [`experiments/H49_h41_power_robustness/protocol.yaml`,
  `experiments/H49_h41_power_robustness/results/power_envelope.json`,
  `airace/h41_power_robustness.py`]
- **Dependencies**: [C38, C44]
- **Tags**: percentile-bootstrap, skewness, Type-I, statistical-power

## C46: Studentization does not yield an eligible H41 gate at n=15
- **Statement**: On the frozen five-family envelope, neither stratified
  Welch-t nor bootstrap-t simultaneously meets H41's small-sample Type-I,
  moderate-effect power, and numerical-stability requirements.
- **Status**: supported by preregistered method comparison
- **Provenance**: ai-suggested
- **Falsification criteria**: A preregistered repair on the same envelope keeps
  every 15-passage Type-I rate in 0.01–0.08, has at least 0.50 worst-family
  power at `d=0.5`, and has at most 1% nonfinite replications.
- **Proof**: [`experiments/H50_h41_inference_repair/protocol.yaml`,
  `experiments/H50_h41_inference_repair/results/method_comparison.json`,
  `airace/h41_inference_repair.py`]
- **Dependencies**: [C45]
- **Tags**: bootstrap-t, Welch-t, small-sample, numerical-stability, power

## C47: Distribution-free bounded gates are vacuous at H41 scale
- **Statement**: Although H41 passage deltas are exactly bounded in `[-1,1]`,
  Hoeffding and stratum-wise empirical Bernstein lower bounds cannot provide
  useful promotion power for the tested bounded families at 15–60 passages.
- **Status**: supported by analytic penalties and preregistered simulation
- **Provenance**: ai-suggested
- **Falsification criteria**: A valid finite-sample bound using only the frozen
  independence and `[-1,1]` assumptions achieves at least 0.50 worst-family
  power at `d=0.75` for n=15 or 0.80 at `d=0.5` by n=60.
- **Proof**: [`airace/metrics.py`,
  `experiments/H51_h41_bounded_gate/protocol.yaml`,
  `experiments/H51_h41_bounded_gate/results/bounded_gate.json`,
  `airace/h41_bounded_gate.py`]
- **Dependencies**: [C45, C46]
- **Tags**: Hoeffding, empirical-Bernstein, finite-sample, bounded-data, power
## C52: Broad WHO-parent insertion harms H38 candidate Jaccard
- **Statement**: Adding a same-family WHO three-character parent beside all 611
  eligible H38 singleton diagnosis codes materially reduces candidate Jaccard
  while leaving WER and assertion scoring invariant.
- **Status**: refuted as a general policy; externally supported negative result
- **Provenance**: ai-executed
- **Falsification criteria**: Reconciliation of the hash-bound submission fails,
  or an exact repeat produces non-invariant WER/assertions and nonnegative
  candidate movement.
- **Proof**: [`experiments/H44_full_who_family_hedge/external_result.json`]
- **Dependencies**: [C40, C51]
- **Tags**: WHO-ICD, candidate-Jaccard, external-result, negative-transfer

## C53: Archive size is not a valid blind submission selector
- **Statement**: The observed file-size/score association is confounded by
  semantic-coverage growth; archive bytes cannot distinguish supported recall
  from formatting, compression or harmful candidate cardinality.
- **Status**: supported by nine-run audit and external counterexamples
- **Provenance**: ai-suggested
- **Falsification criteria**: Within a frozen semantic architecture, archive
  size predicts repeated external score direction without a counterexample and
  independently of canonical entity/assertion/candidate counts.
- **Proof**: [`experiments/H56_semantic_size_proxy/results/audit.json`,
  `experiments/H56_semantic_size_proxy/analysis.md`]
- **Dependencies**: [C52]
- **Tags**: proxy-metric, confounding, recall, compression, black-box-evaluation
