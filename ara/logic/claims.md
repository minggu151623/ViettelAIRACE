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
- **Status**: supported internally; external effect untested
- **Provenance**: ai-suggested
- **Falsification criteria**: Any retained H22 row fails raw-offset validation,
  a calibration dummy survives packaging, identical builds differ, or the
  submitted artifact fails to improve over H20 under the organizer evaluator.
- **Proof**: [`experiments/H22_calibrated_pseudo_reconstruction/build_report.json`,
  `experiments/H22_calibrated_pseudo_reconstruction/proxy_comparison.json`,
  `turn2/output_v7_pseudo_reconstruction.zip`]
- **Dependencies**: [C20, C21]
- **Tags**: pseudo-labels, calibration, reconstruction, external-pending
