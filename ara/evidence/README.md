# Evidence Index

- `tables/h25_h37_span_outer_loop.md`: frozen span-model, calibration,
  agreement, verifier, and H37 integration results.

- External V6 result: `research-log.md` — score 1.7280.
- Weighted training: `models/bami-airace-v15-weighted/training_report.json`.
- V16 run report: `reports/v16_teacher_student.json`.
- Deterministic V16 SHA-256:
  `00f592146e87aa9134d8af4e4d930108247f0f28156719e87588b74066295f00`.
- V18 intervention reports: `reports/v18_evidence_lf.json`,
  `reports/v18_evidence_crlf.json`, and `reports/v18_delta_audit.json`.
- Deterministic V18 CRLF SHA-256:
  `9e4fc10bef807a5ecd800fb577de56f988e5fbc584137bf03705d0c48c3adca0`.
- H22 proxy comparison:
  `experiments/H22_calibrated_pseudo_reconstruction/proxy_comparison.json`.
- Deterministic H22 SHA-256:
  `03651cfea61d989cb3fd5574828d912a04752aca6eb7a0ff2f04f37f4c283ade`.
- External H22 result: `experiments/H22_calibrated_pseudo_reconstruction/external_result.json`
  — score 38.7976, WER 57.2161, assertion 47.5455, candidates 29.2469.
- H23 candidate audit: `experiments/H23_candidate_only_semantic/build_report.json`.
- Deterministic H23 SHA-256:
  `e1fc83b8e53cd9d4ac3f5d7f072a4f34eb46ee7841243a52f690ae8645514662`.
- H39 dependency-aware early gates:
  `experiments/H39_dependency_aware_label_model/results/early_gates.json`.
- H40 repeated-passage stability gates:
  `experiments/H40_repeated_passage_consistency/results/early_gates.json`.
- H41 prediction-blind queue audit:
  `experiments/H41_repeated_passage_blind_annotation/results/queue_audit.json`;
  main queue SHA-256
  `a10b345aea2247cc5843e89894130f43279bd5bfc36c7bfda0c7abd357bd5f08`.
- H42 clustered-inference audit: `tables/h42_cluster_gate.md`; full simulation
  at `experiments/H42_h41_cluster_gate/results/null_simulation.json`.
- Reset-slot H43/H44 selection: `tables/h43_h44_reset_slot.md`; H43 was deleted
  after its temporal-hazard failure and H44 is the deterministic candidate.
- H45 Jaccard-aware cardinality audit: `tables/h45_jaccard_cardinality.md`; dev
  selected singleton output and broad ranked prefixes reduced test utility.
- H46 score-shape calibration: `tables/h46_score_shape_cardinality.md`; a small
  dev gain failed uncertainty and cardinality gates, so test remained unopened.
- H47 assertion leverage: `tables/h47_assertion_leverage.md`; repeated external
  assertion loss covered 36 novel entities but only 0.04605 weighted points.
- H48 H41 power curve: `tables/h48_h41_power.md`; 15 passages control Type-I
  at 0.053 but have only 0.5882 power at `d=0.5`, while 30 reach 0.8034.
- H49 H41 distributional stress test: `tables/h49_h41_power_robustness.md`;
  15-passage Type-I spans 0.0236–0.1126 and robust 80% power at `d=0.5`
  requires 45 passages across the frozen families.
