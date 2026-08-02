# Findings

## 2026-08-02 — H23 isolates the WHO parent hedge

- H22 contains 146 ICD-10-CM candidate uses whose exact code is absent from
  WHO ICD-10 2019 while the same three-character family exists. Of these, 144
  are singleton rows suitable for a two-candidate `[parent, specific]` hedge;
  one row contains two different families and is quarantined.
- H23 changes exactly those 144 diagnosis candidate fields and freezes all
  3,168 entity boundaries, types, assertions, and every drug candidate. All 68
  unique code/parent pairs remain within the same disease family.
- The H22-derived proxy necessarily penalizes these additions, reducing its
  in-sample candidate score 96.4943 -> 90.1840. This is not negative transfer
  evidence because H22's original candidate is encoded as proxy truth.
- H23 is a genuine candidate-only black-box ablation: external WER and
  assertion metrics should remain stable up to evaluator matching effects.

## 2026-08-02 — H22 external jump to 38.7976

- The submitted hash prefix `03651cfea61d` matches the registered H22 archive.
- H22 improves the frozen H20 baseline by **+8.9567**, from 29.8409 to
  **38.7976**. WER improves 66.7969 -> 57.2161, assertion Jaccard improves
  37.7055 -> 47.5455, and candidate Jaccard improves 21.4207 -> 29.2469.
- Weighted gains are +2.87424 text, +2.95200 assertions, and +3.13048
  candidates. All components improve, externally supporting the full
  annotation reconstruction rather than a single-metric exploit.
- The local proxy correctly selected H22 but its 87.0650 absolute score was
  optimistic by 48.2674 points. It is suitable for coarse architectural
  selection, not fine-grained tuning or score forecasting.
- Candidate normalization supplied the largest gain and remains the largest
  weighted headroom. The next clean experiment should freeze H22 extraction
  and assertions and change candidates only.

## 2026-08-01 — Guarded Turn 2 LLM artifact improves all metrics

- `turn2/output_v2_llm_guarded.zip` scored **19.0709**, improving the Turn 2
  baseline `16.6673` by **+2.4036**.
- WER improved `80.3648 → 78.4389`; text credit therefore rose
  `19.6352 → 21.5611` (**+1.9259**, weighted contribution **+0.5778**).
- J_assertion improved `24.9610 → 27.0860` (**+2.1250**, weighted
  contribution **+0.6375**).
- J_candidates improved `8.2212 → 11.1919` (**+2.9707**, weighted
  contribution **+1.1883**), explaining about half of the total gain.
- The score is reproduced exactly by
  `0.3*21.5611 + 0.3*27.0860 + 0.4*11.1919 = 19.07089`.
- All three metrics moving upward supports guarded LLM recovery plus candidate
  adjudication. Because the submission bundled both changes, the leaderboard
  result does not identify their individual causal effects.
- Candidate normalization remains the largest weighted opportunity: despite
  the largest observed gain, J_candidates is still only `11.1919`.


## 2026-08-01 — Turn 2 input correction and guarded LLM rebuild

- The corrected `turn2/input` matches both `input 2` and
  `input_turn2_vong1.zip` byte-for-byte for all 100 records. The submitted
  `turn2/output` validates 100/100 against raw LF offsets; CRLF projection is
  wrong for this round.
- The externally reported Turn 2 result is **16.6673** with WER `80.3648`,
  J_assertion `24.9610`, and J_candidates `8.2212`. The score is reproduced
  exactly by the 30/30/40 formula, making candidate normalization the largest
  weighted lever.
- Six non-empty records (35, 56, 67, 75, 84, 96) had empty output. A Qwen
  broad prompt recovered recall but emitted substantial advice/lifestyle
  noise; a structured prompt was much more precise. The accepted design uses
  structured clinical-prefix proposals plus either two-prompt or repeated-
  answer agreement for prose.
- The guarded entity intervention adds 55 entities only to those six empty
  records: 21 diagnoses, 21 symptoms, 12 test names, and one drug. It leaves
  all 1,486 scored baseline entities in the other 94 records unchanged.
- A constrained two-pass Qwen review examined 343 unique existing candidate
  mappings. The model could only KEEP or DROP retrieved IDs. Subsequent
  ontology guards retained valid parent codes and unauditable unknown-title
  RxCUIs; the final transform removes 104 candidate uses and adds 44 exact,
  locally verified aliases.
- The combined artifact contains 1,540 entities, has no empty records,
  validates 100/100 in raw LF mode, passes 49 tests, and is byte-identical
  across two independent builds. Its ZIP SHA-256 is
  `6fd8212e1d1c77e83dbdfd0de973b197c147ada6eb059c28abe8e0daba2e8dcb`.
- This artifact is locally justified but externally unverified. No competition
  submission was made.

## 2026-07-29 — H7 external confirmation

- The user-reported H7 submission scored **1.7951**, up from the V6 baseline
  **1.7280** (+0.0671).
- The displayed components reproduce the score exactly:
  `0.3*(100 - 99.9145) + 0.3*2.9498 + 0.4*2.2112 = 1.79507`.
  Contributions are 0.02565 text, 0.88494 assertions, and 0.88448
  candidates.
- This is external evidence that the evaluator's entity matcher is sensitive
  to CRLF-projected positions. It does not prove that every semantic edit in
  V18 is correct, but it makes the CRLF branch the only justified next branch.

## 2026-07-29 — V18 external regression

- V18 scored **1.7751**, below H7's **1.7951** by **0.0200**.
- `J_candidates` remained exactly `2.2112`, so the RxNorm changes did not
  produce measurable candidate-score gain in this bundled submission.
- `J_assertion` fell from `2.9498` to `2.8837`, while WER moved only
  `99.9145 → 99.9148`. The semantic bundle should therefore be rolled back
  conceptually to H7 until the assertion/lab interaction is isolated.
- Three local CRLF controls now exist under
  `experiments/H18_semantic_isolation/`. They are not leaderboard artifacts.

## 2026-07-29 — peer ensemble evidence and outer-loop pivot

- A participant reports that a team in the low 40s used roughly eight models
  and rewrote the core source. This is unaudited peer evidence, not an official
  description of the winning system.
- The report is nevertheless consistent with the metric evidence: almost all
  unrealized score lies in span/type matching, while assertion and candidate
  post-processing has produced only small gains or regressions.
- The project therefore pivots from post-processing to a proposal-bank plus
  calibrated, type-specialist merger. V16 already showed that raw union is
  unsafe; model count alone is not the mechanism.
- Locally available foundations are BamiBERT-ViMedNER, VietMed-NER, PhoBERT,
  weighted BamiBERT, a VietBioNER diagnostic checkpoint, and deterministic
  rule/section proposals. The missing component is reliable calibration data.
- **The current core cannot support a real calibrated ensemble.** Model
  proposal directories are serialized through `Entity.to_dict()`, which drops
  `confidence` and `source`. `hybrid.py` then chooses by fixed type ownership
  and overlap/length rather than learned confidence. V16 retains only teacher
  confidence while the student side is reduced to binary overlap. A new
  proposal sidecar/schema is therefore required before adding more models.

## 2026-07-29 — H15 proposal banks and calibration audit

- A separate non-submission `Proposal` schema now retains exact offsets, type,
  confidence, source, assertions, and candidates. The competition JSON schema
  is unchanged. Sidecar round trips and the full codebase pass 45 tests.
- VietMed-NER produced **2,538** proposals over 100/100 records. The first run
  exposed a real null-handling defect for `NSAID`, `doxycyclinebactrim`, and
  `Insulin`: a lexicon hit without an RxNorm alias was dereferenced. The core
  now abstains instead, and the rerun completed without errors.
- The weighted Bami checkpoint produced **2,989** proposals over 100/100
  records. Exact VietMed/Bami agreement is strongly type-dependent: 158 drug
  spans, 128 diagnoses, 436 symptoms, and only 45 test names agree. This is
  useful merger evidence, but not a justification for raw union.
- A second Bami checkpoint produced **2,460** proposals over 100/100 records.
  All-three exact agreement is 91 diagnoses, 414 symptoms, and 37 test names,
  but only 2 drug spans. This rules out a global “three-model vote” and
  suggests drug candidates need a separate lexicon/RxNorm specialist.
- The checkpoint exporter was corrected to load model/tokenizer once per run
  instead of once per record. A rerun produced byte-identical sidecars while
  reducing the Bami-v3 wall time from 35.7s to 12.3s. This confirms the bank is
  deterministic and cheap enough for repeated local ablations.
- VietMed confidence is visibly overconfident relative to its independent
  behavior: its median confidence is above 0.94 for four major types, yet only
  7/49 predictions exactly match the existing nine-record label file. Raw
  confidence therefore cannot be compared across models without calibration.
- The existing `labels/manual_validation.jsonl` is not an independent
  calibration set. V6 matches all 40/40 entities exactly on its nine records,
  while VietMed obtains strict span/type F1 0.157. The perfect V6 result shows
  that this file was used to construct or tune V6, so it cannot estimate hidden
  performance or train an unbiased merger.
- No merged output or submission ZIP was created. The next bottleneck is
  genuinely independent, blinded span/type annotation—not model count.
- A 12-record length-stratified calibration queue is now locked and the
  annotation UI can restrict itself to those ids with no prediction prefill.
  This prevents accidental reuse of V6/model outputs during first-pass review.
- The merger core now aggregates exact span/type proposals into auditable
  feature rows: unique sources, per-source confidence, source count, and V6
  exact/overlap flags. It still cannot emit submission entities; accept/reject
  labels remain deliberately blocked on independent adjudication.

## Current understanding

The task is a hidden-label, offline clinical information extraction problem.
The output contains text spans, entity types, assertions, and candidates.
Because the organizer supplies no ground truth, a public submission is an
expensive black-box measurement rather than a conventional validation set.

The strongest verified direction is conservative structural cleanup:

1. preserve exact raw-text offsets;
2. remove generic headings and nested duplicates;
3. avoid procedure spans when the schema expects clinical concepts;
4. infer diagnosis only from evidence strong enough to justify a diagnosis type;
5. keep drug candidates defensible and strip unsupported ICD candidates;
6. apply assertion logic locally, with section-aware history and family scope.

## 2026-07-29 evidence rebuild

- **V18 is implemented, but is not yet a verified score improvement.** It starts
  from the externally best V6 artifact and applies only preregistered changes:
  23 compound numeric lab rows are replaced with independent name/result spans
  in nine records; assertions are recomputed for 176 entities; and 12 drug
  candidate fields are reranked or abstained using exact RxNorm evidence.
- **The lab change is bounded to existing compound results.** The splitter does
  not add every numeric adjacency it can detect. A row is promoted only when an
  existing V6 `KẾT_QUẢ_XÉT_NGHIỆM` span contains both the supported test name
  and its numeric value. This preserves the H14 manual-review invariants.
- **Coordinate projection remains separable.** V18 exists in LF and CRLF forms.
  Both validate all 100 records. The CRLF form shifts 2,263 of 2,271 entities;
  the semantic LF form is retained so the newline hypothesis is not confused
  with the assertion/candidate/lab interventions.
- **Packaging is reproducible.** Two independent packages of the V18 CRLF
  directory have SHA-256
  `9e4fc10bef807a5ecd800fb577de56f988e5fbc584137bf03705d0c48c3adca0`
  and contain exactly `output/1.json` through `output/100.json`.
- **Submission order remains causal.** The isolated H7 CRLF-only ZIP should be
  measured first. V18 CRLF is justified only if H7 confirms that coordinate
  convention; otherwise the LF semantic bundle is the relevant future branch.

## Patterns and mechanisms

- **Candidate calibration dominates the verified improvement.** The V5→V6
  external delta is exactly explained by the candidate score change; WER and
  assertion values did not move.
- **Recall-oriented additions are risky.** Model union and unconstrained LLM
  output increase false positives and therefore damage the word-level/entity
  component.
- **No ontology evidence, no code.** RxNorm is demonstrated by the official
  examples; ICD behavior is not sufficiently specified. Unsupported diagnosis
  codes are therefore more dangerous than empty candidates.
- **An older organizer example confirms diagnosis candidates exist.** It maps
  one reflux diagnosis to both a parent and a more-specific ICD code. V6's
  improvement from stripping ICD therefore means its guesses were wrong, not
  that diagnosis candidates should remain empty in a mature solution.
- **Organizer examples are policy evidence, not clean gold.** The recovered
  overview changes `WBC` to `TWBC`, suffers strength-formatting damage, and
  contains RxCUIs later challenged as withdrawn. Use it for taxonomy and
  multiplicity, never character-exact supervision.
- **Local holdout results are useful only for direction.** The manual holdout
  has been touched by rule design, so it is not an unbiased estimate of the
  hidden evaluator.
- **Substring boundaries were a concrete precision bug.** The symptom `ho`
  was emitted inside unrelated words such as `thoáng`, `khoa`, `khoảng`,
  `hoặc`, and `cho`. V10 removes 39 impossible token-internal fragments.
- **Assertion scope had two implementation defects.** V6 attached assertions
  to tests/results and used substring family cues. V10 restricts assertion
  types and distinguishes a relative's condition from a relative merely
  reporting the patient's condition.
- **External black-box evidence overruled local correctness intuition.** V10
  improved WER by only 0.0005 but reduced J_assertion by 0.1274 and
  J_candidates by 0.1328, lowering the total from 1.7280 to 1.6368. The next
  experiment must isolate spans, assertions, and candidates separately.
- **Ablation priority is now explicit.** V12 changes only impossible
  token-internal symptom fragments and leaves all assertion/candidate/drug
  decisions from V6 intact. V11 and V13 are held until V12 gives evidence.
- **Earlier token-model inference was not token-model inference.** A stale
  checkpoint marker disabled Hugging Face `model.safetensors` checkpoints and
  silently selected rules. After repair, class-balanced supervised adaptation
  raised the biased local strict F1 from 0.690 to 0.867.
- **Consensus is materially safer than union.** The learned specialist union
  added over 600 mentions; V16 requires agreement between an original medical
  teacher and the supervised student at high confidence and adds only 169
  non-overlapping mentions.
- **Sliding-window token boundaries need raw-word recovery.** Otherwise a long
  record can emit high-confidence fragments such as `G` / `ãy` or partial
  diagnosis phrases at window edges.
- **V16 refuted recall expansion.** Its 169 gated additions reduced the external
  score from 1.7280 to 1.6868; assertions and candidates caused nearly all of
  the regression.
- **The official offsets encode hidden line breaks.** Every published example
  position, including the final end 554, is explained exactly by inserting
  eleven CRLF pairs into the 532-character flattened input. This motivates a
  position-only coordinate ablation on the LF-only public files.
- **H7 is isolated and reproducible.** The CRLF artifact changes only integer
  positions, preserves all 2,254 semantic records byte-for-byte, validates all
  100 files, and packages deterministically. Its leaderboard result will
  directly test whether the evaluator retained CRLF coordinates.
- **Near-zero text credit implicates entity matching, not just NER quality.**
  V6 has 2,254 raw-valid spans but receives only `0.0398%` text score. A
  text-first matcher would credit many obvious exact mentions. CRLF projection
  moves 2,246 entities; the only eight unchanged spans occur before the first
  line break, matching the predicted scope of the coordinate defect.
- **The distributed archive has Windows provenance but LF-only content.** All
  101 `input.zip` entries declare an MS-DOS/NT FAT origin, while the 100 text
  members contain 2,889 LF bytes and zero CR bytes. Combined with exact CRLF
  reconstruction of the official offsets, this supports post-annotation
  newline normalization as a concrete failure mechanism.
- **V6 covers the explicit semantic fields despite near-zero text credit.**
  It overlaps 100% of non-empty current-symptom, diagnosis, test-result, and
  imaging-result fields; 95% of chronic-disease fields; and 95% of admission
  reasons. This field-level audit cannot prove exact entity accuracy, but it
  rules out catastrophic recall as the main explanation for `0.0398%` text
  score and further favors a matching/coordinate failure.
- **External Vietnamese NER corpora do not define the BTC taxonomy.** ViMedNER
  explicitly allows the same phrase to be symptom or disease by context, while
  ViMQ merges symptom and disease and other corpora use diagnostic-procedure
  categories. They are suitable proposal sources, not direct labels for this
  competition.
- **The schema is consistent with an adapted i2b2 task.** Problem maps to
  diagnosis/symptom, test maps to test-name/result, treatment narrows to drug,
  and absent/not-associated map naturally to negated/family. i2b2 boundary
  rules also agree with repeated occurrences, separate independent symptom
  lists, and body-part symptom phrases. This is a policy prior, not proof of
  provenance: BTC makes assertions multilabel and applies history to drugs,
  unlike original i2b2.
- **Assertions should remain multilabel and orthogonal.** Independent clinical
  assertion work separates negation/certainty, temporality, and experiencer,
  matching the competition's list-valued assertion design.
- **Official forum evidence narrows the policy.** Repeated occurrences are
  separate concepts; test results may be textual; supplied units belong in
  result spans; test names and results need not be linked; and assertions are
  explicitly multilabel. Exact position matching and RxNorm fallback remain
  intentionally undisclosed.
- **V6 RxCUIs are active but some are semantically wrong.** All 79 unique codes
  are Active in the current NLM API, ruling out retirement as the main cause.
  At least 15 uses have unsupported extra ingredients, strength conflicts, or
  oral-vs-IV route conflicts because the resolver chose the numerically first
  RxCUI rather than the best-supported concept.
- **The primary i2b2 guideline makes the boundary prior operational.** It specifies
  complete NP/AP spans, modifier retention, one-PP/body-part handling, list
  conjunction behavior, separate occurrences, and exclusion of formatting-only
  headers. Its assertion guideline gives Possible precedence over Absent. These
  rules are useful for boundary/scope hypotheses, but BTC's multilabel assertions
  and historical-drug behavior make direct label conversion invalid. See
  `literature/i2b2_guideline_extract.md`.
- **The official sample rejects a universal compound-symptom boundary rule.**
  It keeps `sốt đau` as one symptom but splits `lo âu mất ngủ` into two, while
  consistently retaining full administration detail in drug spans and stopping
  them before `điều trị`. Boundary changes therefore need phrase-level evidence;
  blindly splitting or merging every adjacent symptom is not policy-consistent.
  See `literature/official_sample_boundary_policy.md`.
- **The 100 inputs are strongly templated translation/restructuring products.**
  `đánh giá tại bệnh viện` occurs in 74 files, `tiền sử bệnh hiện tại` in
  52, and `tiền sử bệnh` in 48; 26 files retain English clinical fragments
  such as `nausea`, `daily`, `bid`, `dced`, and `sp CABG`. This supports
  section-aware modeling and bilingual lexicons, and raises—but does not prove—
  a transferred-label source-corpus hypothesis. See
  `experiments/H_source_generation/analysis.md`.
- **Archive metadata supports batch export.** All 100 text members share one DOS
  timestamp and the same creator/version fields. This is provenance evidence for
  a common export, not evidence of a particular source corpus or label policy.
- **i2b2 is now bounded as a task-family hypothesis, not a recovered source.**
  Primary sources confirm semi-structured notes, the same problem/test/treatment
  families, manual annotations, and DUA-controlled access. No BTC record has
  been aligned to an i2b2 record, so source-label transfer remains unsupported
  and legally/auditably inappropriate without portal access and exact alignment.
- **An independent participant reproduced the candidate-stripping effect.**
  They report that the same 2,311 entities scored `J_candidates=0` with
  ICD/RxNorm codes and `0.8415` after removing every code; an entirely empty
  submission scored `0.1933`. This supports treating `0.1933` as an empty-set
  structural baseline and confirms that unsupported codes can erase candidate
  credit. The report is unaudited peer evidence, not organizer truth.
- **Zero candidate credit with populated codes affects more than one team.**
  A second participant independently reports `J_candidates=0` despite emitting
  codes. It lacks a paired ablation, but corroborates that code presence alone
  provides no partial credit under the hidden convention.
- **V6 conflates family reporter with family experiencer.** Of 19 `isFamily`
  labels, manual context review finds only one plausible relative-owned event
  (`Mẹ ... tử vong`); the other 18 describe the patient, often merely reported
  by family. V6 also places 15 assertions on test/result entities even though
  the metric wording names disease, drug, and symptom. V10 cannot adjudicate
  this because it changed several components at once; an assertion-only
  external test remains necessary.
- **V6 frequently merges laboratory name and value into one result span.**
  At least 52 of 156 numeric results contain an obvious test-name token, and
  18 result spans overlap a separately emitted test name. Official policy says
  names and results are independent and includes units in results when present;
  the organizer overview likewise separates `WBC` from its value. This is a
  concrete boundary/type defect, but it should be tested separately from long
  textual imaging results.
- **The current precision detector has a measurable lab-coverage gap.** On a
  15-row, policy-derived fixture spanning eight records, it recovers both exact
  name and result spans on 4 rows (and at least one span on 5). This is not a
  gold-set score, but it isolates a reproducible implementation target:
  expand only high-confidence lab lexicon/row patterns before considering any
  external artifact.
- **A conservative numeric-row splitter now satisfies the H14 conformance
  fixture.** It recovers all 15 policy-derived name/result pairs, preserves
  explicit units, supports both row orders, and prevents cross-line value
  capture. All 35 project tests pass. The splitter remains disconnected from
  inference, so this is implementation evidence rather than leaderboard
  evidence.
- **Full-input probing exposes context risks before integration.** With the
  fixture names added to the bundled lexicon, the splitter proposes 51 pairs
  across 22 records. Examples such as `rr 14 spo2` and `kali 80mEq` show that
  numeric adjacency alone is insufficient; action phrases, vital-sign context,
  and multi-value panels need explicit gates.
- **Context gates remove the two demonstrated H14 hazards.** Requiring a
  value-before-name row to start its line/semicolon segment and rejecting local
  treatment-action prefixes removes both `spo2 <- 14` and `kali <- 80`.
  The proposed set contracts from 51 to 48 pairs, and all 36 tests pass.
- **H14 now defers unsupported boundary classes instead of truncating them.**
  Glued suffixes (`100ra`) and evolving values (`2.0 -> 3.2`) are excluded from
  the first-stage numeric intervention. The remaining set is 45 pairs across
  19 records, with 37/37 tests passing.
- **H14 has a bounded V6 edit surface.** Of the 45 conservative pairs, 23 are
  fully covered by an existing compound result span and 14 already have both
  independent spans. This supports a narrow split-only ablation rather than a
  broad laboratory rewrite, once the external position test is resolved.
- **H14 is deterministic at the proposal level.** Two full-input runs produced
  byte-identical serialization for all 45 gated pairs, with SHA-256
  `585bde82ced0e1e4a05af90352315c51096d094242c5863ccf13c1b5ed033373` and
  no raw-offset violations.
- **A read-only H14 dry-run affects only nine V6 records.** Split-only edits
  would target records 5, 17, 37, 38, 39, 51, 56, 70, and 84; seven existing
  overlap cases were flagged for manual review. No output file was written.
- **The seven dry-run overlap warnings are explainable.** Each is an existing
  exact/nested test-name span inside the compound result; record 38 contains
  intentional `cr`/`creatinine` aliases. H14 needs deterministic deduplication
  and longest-alias handling, not blanket overlap removal.
- **ViMedNER is the strongest public supervised-transfer candidate, but its
  license is unresolved.** Its expert-annotated disease/symptom/cause/
  diagnostic/treatment taxonomy is substantially closer to BTC than ViMQ,
  VietBioNER, or spoken VietMed-NER.
- **VietBioNER is explicitly licensed CC BY 4.0.** Its README grants the
  license even though GitHub's SPDX field is empty. The official repository is
  pinned locally at commit `19ba70a`; it is approved for attributed boundary/
  diagnostic-procedure research, not direct disease-vs-symptom transfer.
- **A BTC-schema-safe VietBioNER transfer corpus is now prepared.** It retains
  only `DiagnosticProcedure → TÊN_XÉT_NGHIỆM`: 706/300/700 train/validation/test
  sentences with 191/89/202 entities. The source's combined disease/symptom
  class is explicitly excluded.
- **The first licensed transfer model is rejected.** BamiBERT trained on only
  VietBioNER diagnostic procedures reached source F1 0.462745 but precision
  0.355422 (107 false positives for 59 true positives). That is unsafe for
  BTC inference, so the checkpoint is not integrated.
- **Confidence calibration cannot rescue H6.** On the independent source split,
  threshold 0.70 reaches F1 0.525822 but only precision 0.451613; the highest
  nontrivial precision is 0.5 with sharply reduced recall. The checkpoint is
  conclusively excluded from BTC proposal generation.
- **A concrete RxNorm fallback defect is now repaired and unit-tested.** Bare
  generic mentions previously used the first broad product-index value,
  producing unrelated combination products. The resolver now chooses the exact
  CPC alias first; audited regressions map acetaminophen/aspirin/metoprolol to
  `161`/`1191`/`6918`, respectively, and the 40-test suite passes. This is
  semantic conformance evidence only: no submission artifact has been created.
- **The H8 repair has a small, auditable V6 surface.** A read-only re-resolution
  of all 165 V6 drug entities changes eight candidates in six records: seven
  high-confidence generic corrections and one bare-brand (`prograf`) concept
  choice. The brand case stays explicitly separated from a future candidate-only
  ablation; no JSON/ZIP was generated.
- **Route-aware RxNorm reranking is not yet identified with the BTC coding
  convention.** Official RxNav confirms three V6 IV mentions are currently
  mapped to oral tablets, but the previously proposed replacements are SCDC
  strength concepts rather than injection products. The exact route-consistent
  product/form codes differ. Until BTC clarifies whether it wants ingredient-
  strength, form, or packaged-product RxCUIs, that rewrite is deliberately
  deferred.
- **The official sample narrows the route decision enough for an exact-match
  rule, not for a global TTY rule.** Ten of eleven official drug candidates are
  SCD products; the lone no-strength nystatin candidate is IN. The resolver
  therefore now permits an SCD injection only where ingredient, total dose, and
  explicit IV route all agree, and otherwise abstains. A read-only V6 audit
  yields 12 changes: 7 generic fixes, 4 IV fixes/abstentions, and 1 separately
  quarantined bare-brand choice. No output artifact was generated.
- **V11 cannot be read as a pure `isFamily` experiment.** Its non-assertion
  fields exactly match V6, but 176 assertion rows change and 144 of them add
  `isHistorical`. It remains a valid broad assertion-policy artifact, but its
  eventual score cannot isolate the reporter-vs-experiencer hypothesis.
- **The historical portion of V11 has a strong structural rationale.** All 147
  newly historical rows occur in the raw note's explicit numbered history
  section, rather than being triggered by broad lexical proximity. This makes
  V11 a meaningful test of a broader section-aware assertion policy, though
  still not a family-only ablation.
- **The scoreboard formula is now exactly reconstructed on its displayed
  percentage scale.** `final = .3*(100-WER) + .3*J_assertion +
  .4*J_candidates` reproduces V1, V2, V6, and V16. Critical correction:
  0.01194 is V6's **current** text contribution, while the remaining text
  headroom is 29.98806 points. WER near 100% means entity matching is the
  dominant failure, not a saturated metric.
- **The official sample eliminates byte-offset and normalization alternatives
  to H7.** Its first published start is 58: Unicode character position 56 plus
  one CRLF pair, while UTF-8 byte position would be 77. Its final published end
  is exactly `532 + 11*2 = 554`, versus 624 UTF-8 bytes. All 100 inputs are NFC
  and contain no astral characters, so newline normalization is the only
  evidence-supported coordinate discrepancy.
- **Longest-alias handling is now tested.** Calcium panel variants select
  `canxi toàn phần`/`canxi ion hóa` for their respective values without adding
  a generic `canxi` duplicate; the full suite reaches 38 passing tests.

## Lessons and constraints

- **H22 is a calibrated reconstruction, not recovered organizer gold.** The
  collaborator fixture contains 3,168 valid annotations and 940 explicit
  out-of-range dummy entities. Those dummy rows make H20 score 29.8525 locally,
  within 0.0116 of its 29.8409 leaderboard score, but they are only a model of
  unmatched hidden mass and must never enter a submission.
- **The cleaned H22 artifact clears a deliberately large local gate.** It
  validates 100/100, is byte-deterministic, contains no dummy rows, and raises
  all proxy components. The 87.0650 proxy score is an in-sample conformance
  measure, not a forecast; one leaderboard submission is needed to test whether
  the reconstructed annotations transfer to the organizer policy.
- **H22 is independent of H20 by construction.** It does not union H20 rows or
  copy H20 assertions/candidates. This sacrifices some shared-field agreement
  but prevents a calibrated baseline from leaking into its own challenger and
  leaves the external result interpretable.

- **H21 now separates inner-loop evaluation from scarce leaderboard feedback.**
  Its 18-record queue is selected from raw length/structure without accepting a
  prediction directory, fingerprints both corpus and records, and holds out one
  record from each of six strata. The gate fails closed on missing or invalid
  annotations and only an untouched holdout can return `PROMOTE`.
- **The safe fallback is operational, not a hidden-score guarantee.** H20 stays
  frozen whenever the challenger gains less than three proxy points, has a
  non-positive paired-bootstrap lower bound, reduces strict span/type F1, or
  breaches a component floor. This prevents weak challengers from replacing
  the 29.8409 artifact but cannot eliminate organizer-policy shift.

- **H20 is externally supported and establishes a new baseline of 29.8409.**
  Relative to H17, WER improves by 7.2103, assertion Jaccard by 6.9454, and
  candidate Jaccard by 9.4507. Weighted contributions are +2.16309 text,
  +2.08362 assertions, and +3.78028 candidates, totaling +8.02699.
- **The architecture-scale intervention improved every metric simultaneously.**
  This refutes the concern that the 500-row expansion was merely raw recall
  inflation. Exact learned-pair additions plus ontology repair are productive
  on the correct Turn 2 input, although their separate effects are not isolated.
- **Candidate reconstruction delivered the largest weighted headway.** The
  +9.4507 candidate-Jaccard gain accounts for 47.1% of the total score increase.
  Candidate work is no longer a negligible side channel, but span/type recall
  still has substantial headroom because WER remains 66.7969.

- **The H18 selector, not the WHO catalogue, was the immediate candidate
  failure.** It forced old codes through reviewer rejection and could join a
  parent from one family to a child from another. H19 makes review authoritative
  and family-consistent, changing 189 diagnosis candidate fields while freezing
  all other fields.
- **Local-LLM numeric confidence is not a calibrated judge score.** In H20,
  Qwen copied proposal confidences into its response even when making sensible
  categorical decisions. Treating those numbers as probabilities would retain
  only 12/529 rows and discard many obvious clinical mentions.
- **Drug adjudication needs a type specialist, not the generic Qwen action.**
  Qwen rejected obvious medications inconsistently, whereas exact VietMed+Bami
  agreement recovered 82 non-overlapping drug spans. H20 therefore uses Qwen's
  categorical action for diagnoses/symptoms/tests and supervised pair agreement
  for drugs, with deterministic fused-token rejection.
- **H20 is a genuine architecture-scale recall intervention.** It adds 500
  disjoint entities on top of H19 while preserving all 1,950 prior entities
  exactly. Its leaderboard value remains unknown until the user submits it;
  local validity and model agreement are not a claimed score guarantee.

- **H17 remains positive but recall gains are saturating.** Sixty-six additional
  entities raise the score only 0.3400. Further pair-threshold expansion is not
  a breakthrough path and risks turning into an uncalibrated union.
- **The diagnosis pipeline mixes WHO ICD-10 with US ICD-10-CM.** The organizer
  specifies a Vietnamese ICD-10 edition. Thirty-nine current code uses are not
  present in WHO ICD-10 2019 although their three-character WHO categories are.
  Candidate reconstruction must be ontology-locked before further tuning.

- **Independent learned pairs yield a small, auditable next recall layer.**
  VietMed plus one Bami exact agreement and fixed confidence floors reduce the
  pair-only mass to 72 rows; Qwen retains 66. This is a bounded extension of the
  externally successful H16 mechanism, not evidence for accepting correlated
  Bami-only pairs.
- **`phủ nhận` is an essential Vietnamese negation cue.** The assertion engine
  previously missed it; the grammar and regression suite now cover this cue.

- **H16 is externally supported and improves every component.** Adding 344
  exact three-model entities raises the score 19.0709 -> 21.4739. The largest
  gains come from text (+1.1690 weighted points) and assertions (+0.9562), while
  candidates add +0.2778. High-consensus recall is therefore productive on the
  correct Turn 2 corpus, but candidate normalization remains the weakest and
  most heavily weighted absolute component.

- **Correct Turn 2 input unlocks a high-precision learned-model recall core.**
  On the correct LF corpus, VietMed-NER, Bami-v15, and Bami-v3 agree exactly on
  344 previously absent non-drug entities after filtering one malformed drug.
  The agreement concentrates in symptoms (280), with 47 diagnoses and 17 test
  names, and reaches 80 records. This is structurally different from raw union:
  1,267 pair-only proposals remain excluded.
- **Consensus does not eliminate taxonomy error.** A small number of repeated
  surface forms conflict with an existing type elsewhere (notably `bại não`).
  Type reconciliation needs its own protocol; it must not be silently folded
  into the three-way recall experiment.

- **H23 closes candidate-list micro-tuning as a breakthrough axis.** Adding
  144 valid same-family WHO parents improved 38.7976 to 38.9352. WER and
  assertions remained identical, while candidate Jaccard rose only 0.3441.
  The transform is externally valid but too small to close the remaining gap.
- **The local terminology graph is large enough to require learned retrieval.**
  H24 contains 69,991 WHO/RxNorm nodes and 294,548 typed relations. Character
  TF-IDF retrieves the weak target at R@1 10.81% overall but only 2.62% for
  Vietnamese diagnoses, exposing the cross-lingual lexical gap.
- **Unchanged BamiBERT embeddings are worse than lexical retrieval.** Mean
  pooling the frozen NER backbone gives R@1 4.05% overall and 0% diagnosis
  R@1 on dev/test. A Vietnamese NER checkpoint has not learned alignment to
  English ontology titles; separate mention/concept projections and explicit
  contrastive training are necessary.
- **Random projection alignment memorizes weak links instead of learning the
  ontology.** Alignment-only raises train R@1 to 30.28% but reaches 2.78% on
  dev and 0% on test, including 0% for concepts observed in training. The next
  design must preserve the clinical encoder's geometry and expose learning to
  false candidates mined from the complete ontology, not just mini-batches.
- **Clinical mention prototypes are now the bounded next mechanism.** A
  train-only mean embedding per linked concept can test whether Vietnamese
  paraphrases cluster without fitting random heads. BioSyn-style full-ontology
  mining and lexical fusion are conditional follow-ups, not bundled changes.
- **Bami clinical prototypes add a few diagnosis hits but do not generalize.**
  They leave test R@1 at 5.36% and raise test R@5 to 8.93%, while dev R@1
  regresses to 2.78%. The few complementary hits justify later fusion, but the
  dominant bottleneck is now clearly a missing Vietnamese-English retrieval
  encoder rather than a missing graph layer.
- **A dedicated multilingual embedder must precede graph learning.** Graph
  propagation cannot repair query/concept vectors that fail to meet. Qwen3
  Embedding is registered next because it is retrieval-specific,
  instruction-aware and multilingual; it will be tested unchanged before any
  graph or classifier contribution is claimed.
- **Qwen3 Embedding fixes candidate-pool recall, not top-1 calibration.** Its
  test R@10 is 37.50% versus lexical 21.43%, and diagnosis test R@1 reaches
  12.77%; dev R@1 still trails lexical. The semantic encoder is now useful as
  a generator, while top-1 requires specialist fusion and reranking.
- **Diagnosis and drug retrieval require different specialists.** Qwen bridges
  Vietnamese-English diagnosis terms; character TF-IDF remains superior for
  drug ingredients and brand strings. A fixed type switch is better founded
  than a globally tuned sparse/dense weight on only 36 dev rows.
- **The fixed type router is the first H24 retrieval design to generalize.** It
  reaches dev/test R@1 16.67/17.86% and R@5 25.00/30.36%, clearing every
  preregistered sparse-dense gate. The gain comes from architectural division
  of labour, not a tuned interpolation weight.
- **The remaining retrieval error is primarily ranking inside a useful pool.**
  Test R@10 is 39.29% while R@1 is 17.86%; a contextual classifier/reranker can
  in principle recover another 21.43 points without widening proposals. This
  is now a better target for graph and hard-negative methods than raw recall.
- **An unchanged multilingual reranker does not solve ontology ranking.** The
  graph-enriched variant raises dev R@5 within the reranker but leaves selected
  test R@1/R@5/R@10 exactly equal to the fixed router. Generic relevance
  judgments are not calibrated to BTC concept specificity or RxNorm policy.
- **The next classifier must learn from the project's own mined mistakes.** A
  bounded pair model can use dense similarity, sparse rank, exact match,
  context similarity, code depth and graph-family features on train-only hard
  candidates. This changes the source core in the way the peer report implied,
  while retaining a measurable router fallback.
- **Even a project-trained linear linker does not improve top-1.** Context
  cosine receives the largest positive coefficient, but dev/test R@1 remains
  16.67/17.86%; graph features change neither dev R@1 nor R@5. With only 518
  H23-derived weak rows, deeper linker fitting is more likely to overfit than
  to create leaderboard gain.
- **H24's durable result is a candidate generator, not a submission.** Qwen
  diagnosis plus lexical drug retrieval expands held-out candidate pools and
  can support future normalization, but it has not passed an end-to-end gate.
  Research should now target proposal span/type and assertion selection, which
  control the much larger external text and assertion deficits.
- **H24 evaluation remains weak-label evaluation.** The 518 link rows are
  derived from H23 and are not organizer truth. Alias-group splitting prevents
  surface leakage, but a gain only proves the new model can learn the frozen
  pseudo mapping; promotion still requires graph/context ablations and
  conservative external interpretation.
- **Positive-unlabeled calibration cannot rescue correlated proposal errors.**
  H25's Qwen-context PU model improves strict F1 by only 0.39/0.40 points on
  dev/test, with addition precision 41.67/36.84%. Its nominally stable rows
  still contain fused boundaries such as `doxycyclinebactrim` and
  `klonopinclonidine`, showing that Bami agreement is not independent evidence.
- **The existing proposal pool has useful but inaccessible oracle headroom.**
  Perfectly selecting the same disjoint bank candidates would improve held-out
  F1 by 7.64/7.06 points. The bottleneck is proposal adjudication and source
  diversity, not total absence of recoverable spans.
- **Contextual assertion learning is unstable across records.** It improves
  test macro Jaccard by 3.89 points but regresses dev by 3.03 points. The rule
  engine remains safer until a record-held-out method improves both splits.
- **The next independent source should distill repeated annotation policy.**
  High-purity phrases learned only from H23 train records can test whether the
  templated corpus transfers boundaries and types without relying on correlated
  model confidence. This must precede another direct-LLM or PU fusion layer.
- **Train-only phrase policy transfers, but context determines correctness.**
  A 235-entry high-purity lexicon raises held-out strict F1 by 4.08 points on
  dev and 1.32 on test, recovering 43 and 26 true pseudo-target additions.
  This is far stronger than H25 PU, but raw addition precision is only
  50.59/36.11% because phrases such as `mạch`, `phù`, and `bình thường` change
  meaning with context.
- **H23 absence cannot be used as a clean phrase-level negative.** Several
  H23-absent matches are legitimate clinical concepts in context (for example
  a patient actually falling). A contextual verifier should therefore enforce
  semantic boundary/type policy, not merely learn to reproduce H23 inclusion.
- **A KEEP/DROP verifier cannot fix a wrong candidate boundary.** H27 retains
  81.40% of H23-present additions and raises dev strict F1 by 4.06 points, but
  improves pseudo precision by only 10.82 points versus the registered 15-point
  gate. Its residual errors include incomplete `Phù`/`Đau`/`Dị ứng` spans that
  require choosing a complete local span, not another acceptance threshold.
- **H27's apparent false positives are partly unlabeled, not necessarily
  wrong.** Explicit falls, seizures, pneumonia, CT imaging, hypoxia and bleeding
  were absent from H23 yet accepted in clinically coherent contexts. H23-based
  precision remains a conservative diagnostic and cannot authorize a ZIP by
  itself.
- **Boundary choice requires a coverage proof before model evaluation.** H28's
  preregistered ±4-token choice set covered only 325/392 eligible dev targets
  (82.91%), mainly because long mentions need seven-token expansion. The run was
  stopped before LLM inference. Pseudo-target spans with mid-token endpoints or
  outer punctuation must also be excluded from a token-boundary benchmark.

- Keep every experiment deterministic and byte-identical on rerun.
- Treat each leaderboard submission as a preregistered ablation, not as a
  tuning loop.
- Never use a pretrained PhoBERT checkpoint alone as a decision model. V16 uses
  the original medical checkpoint only as one side of a consensus gate with a
  separately supervised student.
- Do not submit combined “obvious” fixes when the only proxy is a saturated,
  hand-tuned holdout.
- A multi-teacher design should use agreement as a confidence signal, not raw
  union. Knowledge distillation is a future training path, not a reason to
  inject arbitrary labels now.
- The generic `lm-evaluation-harness` is not the competition evaluator; use a
  custom competition metric harness and document the mismatch.

## Open questions

### H29 boundary-policy update

- **General semantic completeness is not the annotation boundary policy.** H29
  achieved complete choice coverage but only 37.07% corrupted-span recovery and
  70.13% unchanged-control retention. Qwen frequently selected a surrounding
  grammatical clause or a semantically plausible shorter phrase. A boundary
  model must learn BIO-style inclusion decisions from the project's repeated
  records; prompt wording is not a reliable substitute.
- **Weak-label token adaptation learns recall but not sufficient precision.**
  H30 reaches 72.46% recall but only 57.44% precision and 64.08% exact F1 on
  record-held-out dev. The model has learned reusable clinical spans, but class
  weighting creates 269 false positives. It is not a direct replacement for
  H23; only a preregistered confidence subset may be investigated next.
- **H30 confidence is well ordered across unseen records.** The preregistered
  0.90 threshold selected on dev yields 81.60% precision there and 84.53% on
  one-shot test, with F1 65.63/62.14% and deterministic offsets. This promotes
  H30 only as a high-confidence voter; cross-fitting is required before using it
  on records included in its original training set.
- **Absolute confidence is not portable across cross-fit checkpoints.** H32
  retains 83.06% aggregate precision but falls to 36.68% recall and 50.89% F1;
  one early-stopped fold emits zero spans above 0.90. Each checkpoint requires
  calibration on its own disjoint validation fold before its confidence can be
  compared or thresholded.
- **Early stopping can fire before confidence matures.** H33's per-fold
  calibration still leaves one fold empty. That model stopped at epoch three
  and retained epoch one, while H30's useful precision emerged after epochs
  four through eight. A minimum-epoch safeguard must be tested on the failed
  fold before scaling any seed ensemble.
- **A minimum-epoch safeguard repairs the collapsed fold.** H34 raises that
  fold from zero F1 to 54.35% and yields aggregate OOF precision/recall/F1 of
  82.23/46.15/59.12%. It formally misses the fold recall gate by 0.57 points,
  so no merge is authorized, but future token trainers must not early-stop
  before epoch five under this class-weighted schedule.
- **Independent agreement isolates a compact novel queue.** H35 reduces 316
  H34-new spans to 51 exact agreements: 45 with VietMed, eight with held-out
  phrase policy, and two with both. Many are plausible missed concepts, but two
  known fused-token hazards survive, so source agreement must still be followed
  by semantic and boundary verification.
- **Controlled dual verification passes on the frozen novel queue.** H36 keeps
  27/30 deterministic positive controls, drops both registered fused-token
  hazards, and obtains 92.59% agreement between its semantic and boundary
  prompts. It accepts 42/51 novel rows, including 29 symptoms that can be tested
  without introducing an ICD/RxNorm candidate decision. This authorizes a
  symptom-only integration experiment, not an automatic submission.
- **Verified symptom agreement chiefly identifies H23 boundary inflation.** Of
  29 H36-accepted symptoms, 22 are core spans inside 21 longer H23 symptoms,
  four are disjoint additions, and three conflict with an H23 diagnosis type.
  H37 applies only the first two groups. It removes 314 net boundary characters
  while freezing candidates and all unaffected entities; structural and
  determinism gates pass. External effect is not yet known.
- **H37 confirms the boundary direction but rejects small verified queues as a
  breakthrough strategy.** External WER improves 57.2161 → 56.9633, while
  assertion Jaccard falls 47.5455 → 47.4154 and candidates remain 29.5910.
  The net score gain is only 0.0368. Twenty-six edits cannot close the gap;
  subsequent work must change extraction, assertion, and normalization at
  architecture scale rather than extend H37 with another handful of rows.
- **H38 scales consensus, but correlated model errors remain.** Exact 3-of-5
  agreement plus frozen semantic/boundary verification yields 183 accepted
  changes across 68 records, versus only 26 changes in H37. All registered
  local gates pass, including 91.67% positive-control retention, 100% hazard
  rejection, 90.29% prompt agreement, 100/100 validation and byte-identical
  reruns. Manual anomaly review nevertheless finds a shared error (`38.3°C`
  typed as a symptom) and possible over-specific candidate inheritance after
  diagnosis shortening. Multi-view agreement is therefore a scalable proposal
  mechanism, not a substitute for independent labels.
- **H38 is externally positive but establishes a low ceiling for consensus
  expansion.** Score rises 38.9720 → 39.2813 (+0.3093). The gain comes from WER
  (+0.24171 weighted) and candidates (+0.07464), while assertions lose 0.00702.
  This is a real improvement, but 183 selected rows buy only 0.31 points. Adding
  more rows from the same correlated proposal family cannot plausibly close the
  roughly 11-point gap to 50; threshold tuning on H38 is now a closed axis.
- **H39 separates correlation from policy incompatibility.** The dependency-
  aware EM model beats majority F1 by 11.67 points on the locked correlated-
  noise simulation, proving the implementation can discount duplicated Bami
  errors. Yet it improves only 4/19 real leave-one-family-out cells. The five
  sources are not merely noisy views of one label function: they use different
  boundary/type inventories. No unsupervised source-weighting method can recover
  the missing common policy from these votes alone.
- **Turn 2 contains a latent repeated-passage library.** Exact lines of at least
  40 characters form 271 cross-record groups and cover 43.07% of all input
  characters. H38 is inconsistent on 104 groups. Unlike model agreement, exact
  repeated text is corpus-internal evidence that can support occurrence-level
  transfer, provided assertions remain context-specific.
- **Repetition multiplies labels but does not create them.** H40 retains 97.92%
  of controls, yet canonical stability is only 88.37% and the automatic rewrite
  would touch 551 rows. Exact copies reveal which annotations should be
  consistent, but two-occurrence groups cannot adjudicate conflicting model
  policies. The correct use is prediction-blind annotation of unique passages,
  followed by exact projection—not another automatic modal threshold.
- **H41 turns repetition into a genuine annotation multiplier.** A frozen,
  prediction-blind queue selects 60 passages using only exact text, length,
  distinct-record multiplicity and a deterministic hash. It covers 164
  occurrences across 59 records: reviewing 20,055 unique characters provides
  labels for 55,200 projected characters. The 45/15 development/holdout split
  is fixed before labels, and reviewer 2 receives only a separate 15-passage
  blind queue. This is independent supervision; model comparison remains
  forbidden until both reviewers' files are checksum-locked.
- **Assertion projection must remain occurrence-specific.** Exact passage text
  licenses reuse of relative span/type and cautiously entered candidates, but
  not assertion flags. H41 therefore shows ±200 characters of raw context and
  requires a separate assertion row for every entity occurrence. The validator
  rejects incomplete occurrence coverage and supports multiple simultaneous
  assertions.
- **Repeated occurrences are annotation multipliers, not statistical sample
  multipliers.** H42 simulates the frozen 15-passage/41-occurrence holdout under
  a zero-effect correlated null. At within-passage correlation 0.6, naive
  occurrence bootstrap falsely promotes 10.55% of runs versus 5.43% for the
  stratified passage bootstrap; at correlation 0.9 the rates are 13.28% versus
  5.10%. Both preregistered reduction gates pass. H41 must therefore make
  inference over 15 unique passage clusters and label occurrence-weighted
  results descriptive only.
- **The old record-level blind evaluator is invalid for passage-local gold.**
  H41 does not annotate the rest of a record, so a complete-record scorer would
  turn unknown regions into false negatives or false positives. The H42
  evaluator scores exact passage windows, penalizes spans crossing their frozen
  boundaries, aggregates occurrence-specific assertions within passage, and
  resamples passages inside the frozen multiplicity strata. This repair was
  completed before either reviewer label file existed.

1. Which exact span boundaries/types are systematically wrong on the 100 hidden
   files?
2. Does the RxNorm-only policy improve the external candidate score over V6?
3. Can independent proposal sources be calibrated without a labeled corpus?
4. Can a small, auditable annotation set be constructed from input-only text
   without leaking public-output assumptions?
5. Which assertion labels are over-produced by the current scope rules?
6. After H7 is measured, how much does evidence-consistent RxNorm reranking
   improve candidates without changing spans?
7. Can Vietnamese ICD parent/specific candidate generation be calibrated on
   independently annotated diagnoses without recreating the overview's errors?
