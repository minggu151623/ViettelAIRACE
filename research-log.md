# Research log — Viettel AI Race V1

## 2026-08-04 — H65 second Colab run reaches model loading; translation API incompatibility

- Private clone, Drive copy, 100-file check and CUDA runtime all passed. All
  four pinned model snapshots downloaded successfully on a Tesla T4.
- Execution stopped before inference because the installed Transformers build
  no longer registers the legacy `pipeline("translation")` task. The exact
  exception was `KeyError: Unknown task translation`; the missing report in
  cell 5 was only a downstream consequence.
- Replaced both translation pipelines with a direct batched
  `AutoTokenizer`/`AutoModelForSeq2SeqLM.generate()` wrapper and changed cell 4
  to propagate subprocess failures. Cell 5 now checks report existence before
  reading it. No scientific Stage-0 result or target ZIP exists yet.

## 2026-08-04 — H65 first Colab run blocked by private-repository authentication

- Drive mounted successfully and Colab exposed a Tesla T4 with CUDA-enabled
  PyTorch. The first failing operation was the unauthenticated clone of the
  private `minggu151623/ViettelAIRACE` repository; missing runner/report errors
  were downstream consequences, not model failures.
- Replaced the clone cell with a hidden fine-grained-token prompt using a
  transient Git HTTP authorization header. The token is absent from the clone
  URL and Git remote. Input copying now removes stale destination data and
  requires exactly 100 `.txt` files.
- Model downloads now resolve each Hugging Face `main` revision to its immutable
  commit SHA before downloading, preventing manifest/byte drift. Notebook
  outputs were cleared; Python, notebook JSON and cell syntax checks pass.
- H65 remains unexecuted scientifically: no Stage-0 report, target inference or
  challenger ZIP exists yet.

## 2026-08-04 — H65 notebook simplified after repository publication

- Anonymous `git ls-remote` confirms branch `codex/core-rebuild-h57` is now
  publicly readable. Removed the token prompt and transient auth header from
  the notebook; no token is needed for the next run.

## 2026-08-04 — H65 rerun failure traced to current-directory deletion

- The clone URL and branch were valid. The kernel retained cwd
  `/content/ViettelAIRACE` after the first run; cell 2 removed that directory
  while still inside it, causing Git's `Unable to read current working
  directory` error.
- Added an explicit `os.chdir('/content')` before cleanup. Rerunning cell 2 is
  now idempotent and does not require a runtime restart.

## 2026-08-04 — H65 Colab runner prepared

- Added a deterministic notebook/runner bridge for the preregistered H65
  Stage-0 test. It requires a Colab GPU (`torch.cuda.is_available()`), uses
  the public PhoNER dev split rather than Turn2 for calibration, records model
  revisions/licenses/bytes, and fails closed before target inference if any
  gate fails.
- This terminal cannot attach to a VS Code Colab remote kernel directly. The
  user must select `Kernel → Colab → Auto Connect`, choose a GPU runtime, mount
  Drive and run the notebook cells. The only required input is
  `MyDrive/ViettelAIRACE/turn2/input`; the notebook installs its own Colab
  dependencies and does not require local model downloads.
- Static checks pass; H65 has not been executed and no ZIP is produced.

## 2026-08-01 — External result for Turn 2 guarded LLM artifact

- The user submitted `turn2/output_v2_llm_guarded.zip`; organizer score:
  `19.0709`.
- Components: WER `78.4389`, J_assertion `27.0860`, J_candidates `11.1919`.
- Relative to the Turn 2 baseline, weighted deltas are text `+0.57777`,
  assertion `+0.63750`, and candidate `+1.18828`, totaling `+2.40355` before
  display rounding.
- Decision: promote this artifact to the best externally verified Turn 2
  baseline. Retain guarded proposal recovery and constrained candidate
  adjudication; do not return to raw union or CRLF projection.
- No subsequent submission artifact was generated in this evidence-recording
  step.


## 2026-08-01 — Turn 2 guarded LLM experiment

- Corrected the data identity error: the new Turn 2 input is 100/100 identical
  to `input 2` and validates the submitted output only in raw-LF mode.
- Locked `experiments/H_turn2_llm_guarded_rebuild/protocol.md` before the LLM
  probes. Git preregistration was unavailable because the workspace root is not
  a Git repository.
- Broad Qwen recovered 18-37 entities on five formerly empty records but also
  hallucinated lifestyle/advice spans. Structured Qwen returned 0-23 entities
  and was selected as the primary teacher; broad output is used only as an
  agreement source.
- Implemented `turn2-candidate-review` with two deterministic KEEP/DROP passes
  over 343 retrieved candidate mappings. Raw review proposed 96 unique drops;
  ontology/manual guards limited the applied changes to 104 candidate uses and
  preserved valid parent/unknown-description baseline codes.
- Implemented `turn2-rebuild`: repair only six empty records, preserve existing
  assertions, filter generic/procedure/advice spans, use repeated-answer
  consensus, and apply a small exact ICD correction table.
- Final local artifact: `turn2/output_v2_llm_guarded.zip`, 100 JSON files,
  1,540 entities, raw-LF valid, 49 tests passing, deterministic SHA-256
  `6fd8212e1d1c77e83dbdfd0de973b197c147ada6eb059c28abe8e0daba2e8dcb`.
- No organizer submission was performed.

This log follows the two-loop autoresearch protocol. Results are separated into
confirmatory tests (pre-registered in an experiment protocol) and exploratory
tests discovered during execution.

## 2026-07-26 — Bootstrap

- **Question:** improve the offline clinical entity extraction and candidate
  pipeline without organizer ground truth.
- **Locked evaluation:** local strict span/type holdout, assertion Jaccard,
  candidate Jaccard, schema/offset validation, deterministic byte identity.
  The leaderboard is treated as a black-box external test.
- **Best external baseline:** V6 structural BTC artifact, score 1.7280,
  WER 99.9602, J_assertion 2.9216, J_candidates 2.0991.
- **Key causal ablation already observed:** V6 candidate stripping changed only
  candidate behavior and increased the total by exactly 0.31852, matching the
  score-weighted candidate delta.

## Completed experiments

| ID | Change | Result | Decision |
|---|---|---|---|
| V1 | rule/dictionary baseline | 0.3690 | retained as safety fallback |
| V2 | Qwen hybrid extraction | 1.3060 | retained as proposal source |
| V3 | consensus source | 1.2726 | rejected as primary due external regression |
| V4 | assertion preservation | 1.4075 | partially retained |
| V5 | precision-oriented structural cleanup | 1.4095 | retained |
| V6 | structural cleanup + ICD stripping + coagulation drug rules | 1.7280 | current best |
| V6-ablation | RxNorm-only candidate policy | generated locally | hold for controlled external test |
| V7 | structured Qwen JSON prompt | local holdout F1 0.545 | rejected; prompt format alone is not a gain |

## Current outer-loop interpretation

The dominant bottleneck is not JSON whitespace or package formatting. Candidate
calibration is the only verified source of a large gain. Text score is nearly
flat, so future work must target exact span/type matching rather than adding
more mentions. Assertion score is above 2.9, but its absolute scale must be
interpreted only through the official evaluator; local assertion tests are
diagnostic, not leaderboard truth.

## 2026-07-26 — H1/H3 correctness repair

- Found 39 token-internal symptom fragments produced by substring matching,
  including 33 false `ho` spans inside unrelated words.
- Fixed generation-time lexicon boundaries and cleanup-time recovery.
- Repaired four medication boundaries without changing their RxCUI.
- Found that V6 reattached assertions to tests/results despite the official
  definition applying assertions to diseases, drugs, and symptoms.
- Found that family detection used raw substring matching: `bố` matched
  `bối cảnh`, and `người nhà nhận thấy bệnh nhân ...` incorrectly marked the
  patient's symptoms as `isFamily`.
- Added section-level history inheritance for clinical entities in numbered
  section 1.
- Result: 2,254 → 2,215 entities; 28 tests pass; 100/100 records validate;
  repeated output directories are byte-identical.
- Produced `output_v10_research_precision_btc.zip`. External score is pending,
  so this is not yet marked as a confirmed gain.

## 2026-07-26 — V10 external result (negative)

The organizer scored V10:

| Metric | V6 baseline | V10 | Delta |
|---|---:|---:|---:|
| Final score | 1.7280 | 1.6368 | -0.0912 |
| WER | 99.9602 | 99.9597 | -0.0005 |
| J_assertion | 2.9216 | 2.7942 | -0.1274 |
| J_candidates | 2.0991 | 1.9663 | -0.1328 |

Using the published formula, the contribution deltas are approximately
`+0.00015 - 0.03822 - 0.05312 = -0.09119`.

Decision: mark the combined V10 intervention as a **dead end**. The tiny WER
gain does not compensate for the assertion and candidate regressions. Preserve
V6 as the best submitted baseline and require single-dimension ablations next.

## 2026-07-26 — Single-dimension ablations

Built three deterministic artifacts from the exact V6 source:

| Artifact | Intervention | Entity count | Status |
|---|---|---:|---|
| `v11_assertion_only.zip` | Recompute assertions only | 2,254 | hold; no external evidence |
| `v12_boundary_only.zip` | Remove only 39 token-internal symptom fragments | 2,215 | lowest-risk candidate |
| `v13_drug_boundary_only.zip` | Trim only four drug boundaries | 2,254 | do not prefer after V10 candidate regression |

All three pass 100-record validation and the 9-record holdout remains saturated
at 40/40, so the holdout cannot select among them. `v12_boundary_only.zip` is
the only candidate currently justified for a follow-up black-box test because
it leaves assertions, drug spans, and candidate arrays byte-equivalent to V6.

## Negative-result discipline

- Do not submit raw VietMed-NER union output: standalone holdout F1 was poor.
- Do not submit unconstrained structured LLM output: local holdout F1 was 0.545.
- Do not restore hallucinated ICD codes merely to increase candidate coverage.
- Do not infer that compact JSON formatting changes semantic score.

## 2026-07-27 — V15/V16 learned-model reconstruction

- Found a critical activation defect: inference recognized only the obsolete
  `heads.pt` marker, while every real Hugging Face training run saved
  `model.safetensors`. All earlier “token model” submissions therefore fell
  back silently to rules.
- Fixed checkpoint detection and model reuse. Actual Bami inference now runs
  over all 100 records in about 16 seconds on MPS.
- Added preregistered inverse-square-root BIO class weighting. Reviewed-holdout
  strict F1 increased from `0.690476` to `0.867470` (36 TP, 7 FP, 4 FN), with
  symptom and test-name F1 reaching 1.0. The holdout remains biased toward V6
  and is treated only as a safety diagnostic.
- Rejected the raw V15 union: it added more than 600 learned spans and therefore
  lacked a defensible precision gate.
- Built V16 as a teacher–student consensus expansion. The original medical NER
  teacher and the supervised weighted student must overlap in type/span; teacher
  confidence must be 0.97–0.98; additions may not overlap V6. Semantic filters
  remove treatment procedures from test names and sliding-window fragments.
- V16 preserves every V6 entity and adds 169 gated mentions: 25 diagnoses,
  99 symptoms, and 45 accepted test-name proposals before overlap
  deduplication/report accounting.
- Kept V6 assertion/RxNorm behavior and empty diagnosis candidates because the
  only external causal evidence shows ICD insertion reduced candidate score.
- Artifact: `output_v16_teacher_student.zip`; 100/100 records validate,
  32 tests pass, and two packaging runs share SHA-256
  `00f592146e87aa9134d8af4e4d930108247f0f28156719e87588b74066295f00`.
- External score is pending. V6 remains the best *verified* submission until a
  V16 leaderboard result exists.

## 2026-07-27 — V16 external result and coordinate pivot

V16 scored `1.6868`, below V6 `1.7280`:

| Metric | V6 | V16 | Delta | Weighted contribution |
|---|---:|---:|---:|---:|
| WER | 99.9602 | 99.9619 | +0.0017 | -0.00051 |
| J_assertion | 2.9216 | 2.8475 | -0.0741 | -0.02223 |
| J_candidates | 2.0991 | 2.0528 | -0.0463 | -0.01852 |
| Final | 1.7280 | 1.6868 | -0.0412 | -0.04126 |

Decision: refute the V16 recall-expansion hypothesis and restore V6.

The official example was then reconstructed at the character level. All
published offsets match exactly when CRLF pairs are inserted before the eleven
numbered items: the flat example length `532` becomes the published final end
`554`. Because the distributed files contain LF only, H7 tests whether gold
positions retained CRLF coordinates. H7 changes positions only.

## 2026-07-27 — H7 CRLF position-only artifact

- Added a deterministic projection from LF offsets to CRLF offsets: each
  entity start/end is increased by the number of LF line breaks before it.
- Generated `output_v17_crlf_positions.zip` from the exact V6 source. No
  `text`, `type`, `assertions`, or `candidates` field changed; comparison found
  zero semantic mismatches across all 2,254 entities.
- 2,246 entities moved; start/end shifts range from 0 to 139 characters
  (median 17). The artifact contains exactly 100 deterministic ZIP members.
- Validation passes in explicit `position_mode=crlf`; two package runs are
  byte-identical with SHA-256
  `88282fa37b3afb04320da1123995a505a44f6e120eb1c8c28733b262d271a04e`.
- This is a high-information black-box test of coordinate provenance, not a
  semantic expansion. External score is pending.

## 2026-07-27 — Independent taxonomy audit

Reviewed ViMedNER, ViMQ, a Vietnamese biomedical NER corpus, and clinical
assertion literature. The external corpora use non-isomorphic taxonomies:
ViMedNER separates disease/symptom/cause/diagnostic/treatment, ViMQ merges
symptom and disease, and other corpora include diagnostic procedures. The
same Vietnamese phrase may be symptom or disease depending on context.
Clinical assertion work independently supports orthogonal negation,
temporality, and experiencer dimensions. Decision: retain these datasets as
proposal sources only; do not merge their labels into a submission without a
competition-policy mapping and precision gate.

## 2026-07-27 — Official forum reconstruction and RxNorm audit

Pulled public forum posts through the organizer API and retained only comments
authored by the official administrator. Confirmed repeated-occurrence,
multilabel-assertion, textual-result, unit, and unlinked-test policies. The
organizer explicitly withholds position matching and RxNorm fallback rules.

Audited all 79 unique V6 RxCUIs (162 uses) with NLM's current history API. Every
code is Active, but at least 15 uses contradict mention evidence through extra
ingredients, wrong strength/form, or oral-vs-IV route. Root cause: the resolver
uses the numerically first indexed product before semantic ranking. H8 is
supported as a code defect; implementation/submission is deferred until H7 is
externally measured so coordinates and candidate changes remain separable.

## 2026-07-28 — H7 internal consistency strengthened

No new organizer answer was posted. Re-examined the official V6 metrics:
`WER=99.9602` means only `0.0398%` text credit despite 2,254 raw-valid spans.
This is incompatible with a primarily text-based matcher and strongly suggests
position-gated pairing. CRLF projection moves 2,246 entities; the only eight
unchanged entities all occur before the first LF. This matches the coordinate
hypothesis's predicted failure boundary. H7 remains externally pending and no
new artifact was created.

Archive provenance provides a second independent check: every `input.zip`
member declares an MS-DOS/NT FAT source, but the text payload contains 2,889 LF
bytes and no CR bytes. This does not alone prove conversion, but it is
consistent with Windows-origin annotation followed by LF normalization.

## 2026-07-28 — Recovered organizer overview example

A public snapshot of the original Track 2 overview contains a second example
that predates the current round PDF. It explicitly assigns both a parent and a
more-specific ICD code to one reflux diagnosis, separates symptoms and test
results, and marks historical drugs. This revises the interpretation of V6:
removing ICD improved the score because its ICD predictions were incorrect,
not because diagnosis candidates are absent from gold.

The snapshot is not character-exact evidence: it changes `WBC` to `TWBC`,
damages decimal strengths, and includes RxCUIs later disputed on the organizer
forum. It is recorded as high-level policy evidence only; no output artifact
or hard-coded annotation was generated.

## 2026-07-28 — Structured-field coverage audit

Audited V6 against the semi-structured headings in all 100 inputs. V6 overlaps
every non-empty current-symptom, diagnosis, test-result, and imaging-result
field; 20/21 chronic-disease fields; and 73/77 admission-reason fields. The
uncovered admission reasons are procedure-only. Medication coverage is lower
(12/17), with one definite miss (`coumadin`) plus broad classes and non-drug
descriptions.

This is not entity-level gold, but it rules out globally catastrophic semantic
recall as the mechanism behind only `0.0398%` official text credit. H7 is
strengthened; no output variant was generated.

## 2026-07-28 — i2b2 policy correspondence

Reviewed the original i2b2/VA concept and assertion documentation. The BTC
schema is structurally consistent with an adaptation: problem is split into
diagnosis/symptom, test into name/result, treatment narrowed to drug, absent
maps to negated, and other experiencer maps to family. Independent i2b2
boundary rules support separate repeated occurrences, splitting independent
symptom lists, and retaining body-part phrases.

The mapping is not exact: original i2b2 assertions are mutually exclusive and
formally apply only to problem concepts, while BTC explicitly uses multilabel
assertions and demonstrates historical drugs. Decision: use i2b2 only as a
manual-boundary prior, never as mechanically converted training gold.

The primary PDFs were extracted into `literature/i2b2_guideline_extract.md`. This
turn records the operational rules (complete NP/AP, PP test, list splitting,
occurrence separation, header exclusion, and Possible-over-Absent precedence);
no output artifact or submission was generated.

## 2026-07-28 — official sample boundary audit

Visually rechecked pages 2-6 of the organizer PDF and compared every medication/
indication boundary with the i2b2 prior. The sample consistently keeps dosing
modifiers inside drug spans, stops before `điều trị`, and emits repeated
occurrences separately. It also contains a decisive within-sample ambiguity:
`sốt đau` is one symptom span, whereas `lo âu mất ngủ` is split into two.
Therefore no global compound-symptom split/merge rule is justified. Findings
were recorded in `literature/official_sample_boundary_policy.md`; no output
artifact or submission was generated.

## 2026-07-28 — source-generation audit

Scanned all 100 public records for normalized repeated headings and residual
English. The dominant three-section template appears in most files, and 26
records preserve English clinical strings or abbreviations. Together with the
i2b2-like target schema, this makes a translated/restructured source corpus a
plausible generation mechanism. Exact-source web searches did not recover an
indexed original, so named provenance remains unproven. The practical result is
to prioritize template/section features and bilingual proposal sources, not to
mechanically import i2b2 labels. No artifact or submission was generated.

A follow-up metadata check found all 100 text members share one DOS timestamp and
the same ZIP creator/version fields. This reinforces common batch export but adds
no corpus identity or annotation gold, so no artifact was generated.

Primary i2b2 challenge and access pages were then checked. They confirm that the
2010 corpus contains semi-structured discharge/progress notes from three
hospital sources (including MIMIC II), uses the matching task families, and is
distributed under a Data Use Agreement through the n2c2 portal. This narrows H12:
task-family resemblance is strong, but named-source provenance and record-level
alignment remain absent. No unofficial mirror was used and no artifact was
generated.

## 2026-07-28 — test-name/result boundary audit

Audited all 329 V6 test names and 235 results against the organizer's independent
name/result policy. Of 156 numeric results, at least 52 contain an obvious
test-name token; 18 overlap a separately emitted name and 16 fully contain that
name. This exposes a systematic compound-row error (`creatinine 5.7`,
`troponin 0.01`, `ast 421`) rather than isolated lexicon noise. Long textual
imaging results remain a separate policy case because the organizer explicitly
allows textual results. No output artifact or submission was generated.

The H14 intervention was then preregistered in
`experiments/H_test_result_boundary_audit/protocol.md`: only high-confidence
numeric lab rows may be split, with all other fields frozen. The protocol
explicitly blocks a leaderboard submission until H7 is resolved and forbids
combining position, assertion, or candidate changes.

A policy-derived fixture was added at `labels/policy_lab_numeric_fixture.jsonl`: 15
numeric laboratory rows from eight records, with raw-text offsets for independent
test-name and result spans. It covers both name/value orders, parenthetical aliases, and
a percent-valued measurement. This is a conformance fixture derived from the official
policy, not organizer gold or a leaderboard-tuned pseudo-label set.

The current precision detector recovered both exact spans for 4/15 fixture rows and at
least one exact span for 5/15. Because the fixture is policy-derived rather than
exhaustive gold, this is recorded only as a coverage diagnostic; it does not justify a
leaderboard artifact. It identifies a concrete next implementation target: expand
high-confidence lab lexicon coverage and support both numeric row orders under H14.

The public forum index was then exhaustively paginated across all 148 posts visible at
capture time. Every commented Track-2/medical-policy post was checked for organizer
authors. No newer organizer clarification was found beyond the already captured rules;
position matching, RxNorm fallback/TTY selection, and candidate matching remain
deliberately unspecified. This prevents treating participant speculation as policy.

Implemented an opt-in conservative numeric laboratory splitter and tests. An initial
test exposed an important cross-line bug: the generic whitespace/range pattern could
attach `13.9 - 80` across adjacent bullets. The pattern was restricted to horizontal
whitespace and normalized `là` was handled explicitly. The corrected splitter recovers
all 15 fixture pairs, rejects a textual `âm tính` result in numeric-only mode, preserves
units, and the complete suite passes 35/35. It remains disconnected from inference and
no artifact was produced.

An input-only risk probe using the fixture names plus the bundled lab lexicon proposed
51 pairs in 22 records. Manual review identified `rr 14 spo2`, `kali 80mEq`, and
multi-value panels as context hazards. This is evidence for adding action/vital-sign
gates before any isolated H14 artifact; no broad rewrite was generated.

Added two preregistered-risk gates to the opt-in splitter. Value-before-name rows
must begin their line/semicolon segment, while name-before-value rows with local
treatment/action cues are rejected. On the 100 inputs, proposals decreased from
51/22 records to 48/21; the two demonstrated hazards disappeared and the full
suite passes 36/36. The splitter remains outside inference.

A second manual risk pass found glued suffixes (`100ra`) and multi-value trends
(`2.0 -> 3.2`, `1.1-->0.8`). Because H14 preregistered deferral of ambiguous
multi-value rows, the splitter now rejects both classes. The proposal set is
45 pairs in 19 records and the suite passes 37/37; inference remains unchanged.

Two consecutive full-input H14 runs were byte-identical (45 rows; SHA-256
`585bde82ced0e1e4a05af90352315c51096d094242c5863ccf13c1b5ed033373`) and all
raw-text offset assertions passed. This confirms deterministic proposal generation;
it is not leaderboard evidence.

A read-only split simulation against V6 would change only nine records
(`5, 17, 37, 38, 39, 51, 56, 70, 84`). Seven existing nested/overlapping
entities were flagged rather than rewritten. This bounds the eventual artifact
surface without generating or submitting a variant.

Comparing the 45 gated pairs to V6 shows 23 compound result spans fully cover a
name/value pair, while 14 pairs already have both exact independent spans. H14 therefore
has a bounded split surface; no output was changed because the position-only H7 test is
still externally pending.

The seven overlap warnings were inspected: all are exact/nested test-name spans
inside the compound result, including the `cr`/`creatinine` alias pair. This
narrows the implementation risk to deterministic deduplication and longest-alias
selection; no unrelated concept overlap was found.

## 2026-07-28 — RxNorm bare-ingredient conformance repair

Reproduced the H8 root cause in the resolver: with no strength, it selected the
first lexicographic ID from the broad product index (`acetaminophen -> 1006887`,
`aspirin -> 1052415`, `metoprolol -> 1162132`), despite those being unrelated
combination products. The resolver now prioritizes the exact bundled RxNorm CPC
alias for bare `IN`/`PIN`/`MIN`/`BN` mentions before consulting product IDs.
Focused regressions yield `161`, `1191`, and `6918`; the full suite passes
40/40. This is a source-backed code conformance repair only. No JSON, ZIP, or
competition submission was generated, and route-aware brand cases remain
separate work.

A read-only re-resolution over the 165 existing V6 drug entities changes eight
candidate fields across six records. Seven are strong generic corrections
(three metoprolol, three acetaminophen, one aspirin); one bare `prograf` changes
from a 5 mg branded product to the exact brand concept. The latter is recorded
as semantically defensible but unverified against organizer policy, so it must
not be silently bundled with generic corrections. The audit tool and JSON
report are retained under `experiments/H_rxnorm_active_audit/`; no output
artifact exists.

Verified the three IV route contradictions against the official RxNav
relationship endpoint. This corrected an overstatement in the earlier audit:
the often-returned codes `315971`, `315502`, and `330371` are SCDC
ingredient-strength concepts, not injection products. RxNav exposes actual
route-consistent product/form alternatives, but there are several defensible
RxNorm abstraction levels (SCDC, SCDF, SCD). Since the BTC has not specified
the intended term type, route rewrites are now explicitly deferred rather than
treated as an automatic fix. The source URLs and all codes are captured in
`experiments/H_rxnorm_active_audit/results/route_concept_audit.json`.

Audited all 11 medication candidates from the organizer's round-1 fixture with
the official RxNav properties endpoint: 10 are SCD product concepts and the
only no-strength nystatin example is IN. This supports a narrow
ingredient+total-strength+explicit-route SCD selection rule—not universal TTY
normalization. The bundled CPC catalog was mechanically rebuilt with 4,139
direct brand-to-generic relations from `RXNREL.RRF`; a local route-aware resolver
now maps exact IV Lasix/levofloxacin examples to SCD injections and abstains on
bumetanide where no exact injected package exists. It passes 41/41 tests.
Read-only V6 re-resolution changes 12/165 drug candidates (7 generic, 4 IV,
1 bare-brand), and no JSON/ZIP submission artifact was created.

Audited four public Vietnamese medical NER sources from their papers, repository
trees, and license metadata. ViMedNER is technically the closest supervised source
(disease, symptom, cause, diagnostic, treatment; ~3 MB of train/dev/test text), while
VietBioNER is useful mainly for biomedical boundaries. ViMQ is dialogue-domain and
VietMed-NER is spoken/ASR-domain. The initial GitHub SPDX-only check incorrectly
classified VietBioNER as unlicensed; its README explicitly grants CC BY 4.0.
The official repository was therefore pinned read-only at commit `19ba70a`, and
split checksums were recorded. ViMedNER, ViMQ, and VietMed-NER remain blocked.

Prepared a deterministic VietBioNER transfer corpus and added a CLI command:
`python -m airace prepare-vietbioner-transfer`. Only `DiagnosticProcedure` is
mapped to `TÊN_XÉT_NGHIỆM`; all other source classes are excluded. The resulting
706/300/700 train/validation/test rows retain 191/89/202 entities and pass exact
offset validation. This prepares a source-only model experiment, not a BTC output.

Ran the preregistered VietBioNER diagnostic-only transfer experiment. It early-stopped
after four epochs; best independent source F1 was 0.462745, with precision 0.355422
(59 TP / 107 FP / 30 FN). The model is rejected as a BTC proposal source because its
false-positive rate violates the precision-first lesson. No output artifact was made.

Calibrated H6 confidence on the independent source validation set rather than the BTC
inputs. The best F1 is 0.525822 at threshold 0.70 but precision remains 0.451613;
the maximum nontrivial precision is 0.5. Thresholding cannot make this checkpoint a
safe BTC proposal source, so H6 is conclusively rejected.

Added a regression for overlapping calcium aliases. The splitter selects the longest
supported name per value and suppresses the generic subspan; the full project suite
passes 38/38. This remains an opt-in implementation test only.

Created an H14 manual-review queue for the five highest-risk contexts and locked
four invariants: exact raw offsets, target-only edits, frozen non-target
assertions/candidates, and deferral of ambiguous rows. This is a review-control
artifact only; it contains no organizer labels and produces no submission.

## 2026-07-28 — independent candidate ablation

A new participant forum post reports a controlled candidate-only change on the
same 2,311 entities: `J_candidates` was 0 with ICD/RxNorm codes and 0.8415 after
all codes were removed. A fully empty 100-file submission scored 0.1933 on the
same metric. This independently confirms V5 -> V6's direction and reveals that
0.1933 is compatible with an empty-set structural baseline, not successful
linking. The claim is not organizer-verified and the artifacts are unavailable,
so it was recorded as peer black-box evidence only. No artifact or submission
was generated.

A second participant independently reported exactly zero candidate credit despite
populated codes. Because that report has no paired abstention run, it was added
only as corroboration, not as a new quantitative ablation.

## 2026-07-28 — outer-loop assertion audit

Reviewed every V6 assertion after the recent policy/provenance synthesis. V6 has
19 `isFamily` labels, but only the file-77 maternal death is a plausible
non-patient experiencer; 18 labels confuse a relative reporting the patient's
condition with a condition belonging to the relative. V6 also assigns 15
assertions to test/result entities, outside the concept families named by the
assertion metric description. V10's regression is not dispositive because it
combined boundary, assertion, and candidate changes. The existing V11
assertion-only artifact is the isolated test; no new artifact or submission was
generated.

## 2026-07-28 — V11 assertion-scope correction

Audited V11 against V6. It preserves all non-assertion fields exactly, but
changes 176 assertion rows: 144 add `isHistorical`, 16 remove `isFamily`, 10
remove `isNegated`, and six make other mixed changes. It is therefore a broad
assertion recalculation, not a direct test of the reporter-vs-experiencer
hypothesis. The delta is reproducible in
`experiments/H_assertion_policy_audit/results/v11_delta_audit.json`; no new
artifact was generated.

The newest forum post was also checked. It is a participant question about the
daily submission quota with no organizer answer, so it changes no Track-2
annotation policy.

The 144 direct and three mixed V11 additions of `isHistorical` were classified
against raw note structure. All 147 occur in the explicit numbered history
section; none comes from a loose nearby cue. Thus V11's broader assertion
change has a reproducible section-policy rationale even though it remains
unsuitable as an isolated family-label test.

Reconstructed the public leaderboard formula against four independently
reported submissions: `0.3*(100-WER) + 0.3*J_assertion + 0.4*J_candidates`.
It exactly reproduces the shown totals after rounding.

Correction: the first interpretation inverted contribution and headroom.
`0.01194` is V6's current text contribution; WER=0 would add `29.98806`
points. Text/entity matching is therefore the dominant failure. Candidate and
assertion research remains relevant, but cannot substitute for repairing the
near-zero text match. The corrected reconstruction is stored in
`experiments/H_metric_reconstruction/`.

Tested H7 against competing offset conventions using the official Vietnamese
prefix. Published start 58 equals Unicode position 56 plus one CRLF; UTF-8 byte
position would be 77. Published final end 554 equals `532 + 11*2`, while the
UTF-8+CRLF length is 624. All distributed inputs are NFC and have no astral
characters, making Python code points and JavaScript UTF-16 units equivalent.
This rules out byte offsets, surrogate differences, and Unicode normalization;
CRLF removal is the sole evidence-supported coordinate discrepancy. No new
artifact was generated because the locked H7 ZIP already implements it.

## 2026-07-29 — H7 external result

The user submitted the isolated `output_v17_crlf_positions.zip`. The evaluator
reported score `1.7951`, compared with the V6 score `1.7280`, an increase of
`0.0671`. The component values were WER `99.9145`, J_assertion `2.9498`, and
J_candidates `2.2112`; the reconstructed formula gives `1.79507`, matching
the displayed rounded total.

This externally supports H7: the hidden evaluator is using a position convention
compatible with CRLF projection. It does not validate V18's semantic changes,
so the next candidate is the already-built `output_v18_evidence_crlf.zip`,
not a new micro-variant.

## 2026-07-29 — V18 external regression

The user submitted `output_v18_evidence_crlf.zip`. The evaluator returned
`1.7751`, which is `0.0200` below H7's `1.7951`. WER changed only from
`99.9145` to `99.9148`; J_candidates stayed exactly `2.2112`; J_assertion
dropped from `2.9498` to `2.8837`. The regression is therefore concentrated
in assertion/entity matching, not candidate resolution.

No causal attribution is made between the lab and assertion interventions,
because V18 bundled them. Three unsubmitted local controls were generated
under `experiments/H18_semantic_isolation/`: assertions-only+CRLF, labs-only+
CRLF, and RxNorm-only+CRLF. They all validate 100/100 records and are for
analysis only; no further ZIP was submitted.

## 2026-07-29 — core-ensemble pivot

The user relayed a participant comment that a low-40s team used approximately
eight models and rewrote the source core. The claim is not independently
audited and does not identify models, training data, or merger policy, so it is
recorded only as peer directional evidence.

An inventory confirms local availability of BamiBERT-ViMedNER, VietMed-NER,
PhoBERT, two internally fine-tuned BamiBERT checkpoints, a rejected
VietBioNER diagnostic checkpoint, and the rule/section system. The outer loop
therefore pivots from semantic post-processing to a type-specialist proposal
bank and calibrated merger. No model union or submission artifact was created.

Core inspection identified the first blocking implementation defect for that
pivot: `Entity.to_dict()` intentionally emits only competition fields and
silently drops proposal confidence/source. All stored model outputs therefore
lose the evidence needed for calibration. Existing `hybrid.py` uses fixed
type routing and longest-overlap selection, while V16 uses only teacher
confidence plus binary student agreement. The rewrite must introduce a
separate proposal schema/sidecar rather than overload submission JSON.

## 2026-07-29 — H15 evidence-preserving proposal core

Implemented a separate proposal schema and optional detector sidecars so model
confidence/source survive serialization without changing competition JSON.
The protocol is locked in `experiments/H15_core_ensemble/protocol.md`; 45 tests
pass.

The first VietMed run failed on records 4, 13, and 37. A traceback isolated a
candidate-resolver null dereference when a lexicon ingredient lacked a catalog
alias (`NSAID`, `doxycyclinebactrim`, `Insulin`). The fallback now checks for
alias evidence and otherwise abstains. The rerun produced 2,538 proposals over
100/100 records with no errors.

Added a generic trained-checkpoint proposal exporter and generated 2,989
weighted-Bami proposals over 100/100 records. Exact VietMed/Bami agreement was
128 diagnoses, 158 drugs, 436 symptoms, and 45 test names. Agreement is
heterogeneous enough that a single global vote threshold is not justified.

A second Bami checkpoint was exported without errors: 2,460 proposals over
100/100 records. Exact agreement across VietMed, Bami-v15, and Bami-v3 was 91
diagnoses, 414 symptoms, 37 test names, and only 2 drugs. The model ensemble
therefore needs type-specific specialists; a global vote would systematically
discard the drug branch.

The exporter was then rewritten to load each checkpoint once per run. A
byte-for-byte sidecar rerun matched the original and reduced Bami-v3 runtime
from 35.7s to 12.3s.

Calibration evaluation uncovered a circularity: V6 matches all 40 entities in
the nine-record `manual_validation.jsonl` exactly. That set cannot be reused as
an independent holdout or as evidence that V6 policy matches organizer gold.
No merged output or ZIP was created.

A 12-record length-stratified queue excluding the old manual records was locked
in `calibration_manifest.json`. The annotation UI now accepts an explicit
record list and can run with a nonexistent prediction directory, preventing
proposal prefill. This is the first usable path to genuinely blinded merger
calibration; it awaits human adjudication.

Implemented the first merger-core layer: exact span/type proposals are grouped
across banks, duplicate proposals from one source retain only that source's
maximum confidence, and each row records unique source count plus V6 exact and
same-type overlap evidence. It produces calibration features only, never
submission JSON. The suite now passes 46 tests.

## 2026-07-29 — integrated evidence rebuild

Implemented `python -m airace evidence-rebuild` with independent feature flags
for assertion refresh, RxNorm refresh, numeric-lab splitting, and CRLF position
projection. The transform always validates its V6 source in raw LF coordinates
before mutation, validates semantic output again, and validates projected output
against CRLF coordinates. JSON uses the organizer-style stable serializer.

The H14 implementation uses the bundled lexicon plus the 15 policy-fixture
aliases, but only promotes a pair when a V6 compound result already covers both
the test name and numeric value. It removes 23 compound results and adds 23
exact numeric results plus 17 missing exact test names across the same nine
records identified by the read-only audit. It does not promote the other
numeric proposals.

The all-evidence LF build changes 176 assertion rows and 12 RxNorm fields
(11 replacements and one abstention). It contains 2,271 entities, validates
100/100 records, and passes the complete 43-test suite. The corresponding CRLF
build shifts 2,263 positions and also validates 100/100 records.

Created deterministic artifacts:

- `output_v18_evidence_lf.zip`, SHA-256
  `b5e4be7d4eba67e19cc3cdf1569cab57bc3db255c48b4bd21448ecb7c4c9cdb9`;
- `output_v18_evidence_crlf.zip`, SHA-256
  `9e4fc10bef807a5ecd800fb577de56f988e5fbc584137bf03705d0c48c3adca0`.

The CRLF ZIP was packaged twice and both hashes matched. Each archive contains
exactly 100 members under `output/`. No competition submission was made. H7
position-only remains the first recommended measurement because it isolates
the dominant coordinate hypothesis; V18 is an externally unverified follow-up.

## 2026-08-01 — H16 Turn 2 multi-model core

- Locked a confirmatory protocol against the externally supported 19.0709
  guarded baseline.
- Regenerated independent VietMed-NER, Bami-v15, and Bami-v3 proposal banks on
  the correct Turn 2 LF input; VietMed ran without baseline reference.
- Found 345 unseen exact three-way span/type agreements. Rejected the sole drug
  row because it is a malformed fused token and admitted 344 diagnosis,
  symptom, and test-name rows.
- Preserved all 1,540 baseline entities and all existing fields. New diagnosis
  candidates use literal alias lookup only; pair-only proposals remain
  quarantined.
- Built `turn2/output_v3_ensemble_core.zip`: 1,884 entities, 100/100 valid
  records, 51 tests passing, deterministic SHA-256
  `24c12c819c5f6afd2dec4fb07d1f75c35b96c2f1a2229ef457d551952131dc2d`.
- No competition submission was performed.

## 2026-08-01 — H16 externally supported at 21.4739

- The user submitted the deterministic H16 artifact and reported score 21.4739.
- Relative to 19.0709: WER improved 78.4389 -> 74.5424, J_assertion improved
  27.0860 -> 30.2734, and J_candidates improved 11.1919 -> 11.8865.
- Formula decomposition attributes +1.16895 points to text, +0.95622 to
  assertions, and +0.27784 to candidates, totaling +2.40301.
- This externally supports exact three-model recall additions and justifies a
  bounded H17 independent-pair layer. It does not justify raw union.

## 2026-08-01 — H17 independent-pair/Qwen artifact

- Preregistered VietMed plus one-Bami exact agreement with type-specific
  thresholds; excluded drugs, results, three-way H16 rows, and Bami-only pairs.
- 72 rows were eligible. Two temperature-zero Qwen seeds returned identical
  decisions and retained 66: 46 symptoms, 16 diagnoses, four test names.
- Corrected a newly exposed assertion bug: `phủ nhận` now triggers
  `isNegated`; added a regression test.
- Built `turn2/output_v4_pair_qwen.zip` with 1,950 total entities. 54 tests pass,
  100/100 files validate, and repeated ZIP SHA-256 is
  `f217efeb117611338dc5dd810058f8cd45fb2e5c60fe9622d370ce09aabf9ce1`.
- No submission was performed.

## 2026-08-01 — H17 externally positive but saturating; pivot to H18

- The user reported H17 score 21.8139: WER 74.0072, J_assertion 30.7601,
  J_candidates 11.9700.
- Relative to H16, the weighted gains are +0.16056 text, +0.14601 assertions,
  and +0.03340 candidates, totaling +0.33997.
- The next recall tier is therefore not a plausible breakthrough mechanism.
- Ontology audit found 39/388 coded diagnosis uses absent from WHO ICD-10 2019
  but mappable to a valid WHO parent, plus 126 uncoded diagnosis entities.
- Preregistered H18 as a candidate-only WHO ICD-10 reconstruction.

## 2026-08-01 — H18 failure audit and H19 candidate reconstruction

- Ran a frozen Qwen proposer/reviewer over 273 unique diagnosis surfaces using
  the 12,221-code WHO ICD-10 2019 catalogue.
- Rejected the direct H18 output before packaging: it preserved old codes even
  when the reviewer rejected them, selected codes alphabetically across
  unrelated families, and accepted malformed confidences above 1.0.
- Registered H19 as a new policy. The reviewer is authoritative, parent/child
  pairs must share a three-character family, anatomy/procedure surfaces are
  pruned, and a finite exact correction table fills high-certainty WHO codes.
- H19 changes 189 diagnosis entity fields: 62 empty fills and 127 repairs or
  removals. It freezes every text/type/position/assertion and every non-diagnosis
  candidate from H17. All 100 records validate and 57 tests pass.
- `turn2/output_v5_who_precision.zip` is deterministic with SHA-256
  `26c8fa1d31dcebeb3019dfe5890abf4f7a264c6b27fd46c532ef7dc13a870104`.

## 2026-08-01 — H20 expanded learned-pair architecture

- Registered a separate recall experiment on top of H19. Retrieved 529 exact,
  disjoint two-model span/type agreements using source/type-specific floors;
  overlapping proposals were excluded before review.
- Qwen's categorical decisions kept 250/256 symptoms, 135/139 diagnoses and
  41/49 tests, but its numeric confidence copied the input model confidence.
  Confidence thresholding was therefore rejected as uncalibrated evidence.
- Qwen also rejected obvious medication names inconsistently (including
  omeprazole and acetaminophen). The final registered selector uses categorical
  Qwen decisions for non-drugs, exact VietMed+Bami agreement for drugs, and a
  deterministic malformed-boundary sanitizer.
- The final H20 layer adds 500 disjoint entities: 134 diagnoses, 247 symptoms,
  37 test names and 82 drugs. It adds 76 historical and 18 negated assertions;
  79 added rows receive exact WHO/RxNorm candidates.
- All 1,950 H19 entities are preserved exactly. The 2,450-entity output passes
  57 tests and validates 100/100 records. Repeated packaging gives SHA-256
  `ad5ac42a2fc3d0105537c42873d4aaeba1e24aef57ec9510216cf32f43d25691` for
  `turn2/output_v6_expanded_pair.zip`.
- No competition submission was performed.

## 2026-08-01 — H20 externally confirmed at 29.8409

- The user submitted the deterministic H20 archive; the displayed hash prefix
  `ad5ac42a2fc3...` matches the registered local artifact.
- Score improved `21.8139 -> 29.8409` (**+8.0270**).
- WER improved `74.0072 -> 66.7969`, contributing +2.16309 weighted points.
- J_assertion improved `30.7601 -> 37.7055`, contributing +2.08362.
- J_candidates improved `11.9700 -> 21.4207`, contributing +3.78028.
- The three weighted deltas sum to 8.02699, reproducing the displayed score
  change. This externally supports both major H20 mechanisms together:
  reviewer-authoritative candidate reconstruction and 500 disjoint learned-pair
  entity additions. Their individual causal contributions remain confounded.
- H20 is now the frozen baseline. Further work must not tune thresholds blindly
  against this one public score.
## 2026-08-02 — H21 blind promotion infrastructure

- Preregistered H21 before selecting records or running the evaluator.
- Corrected the frozen baseline in `research-state.yaml` from H17/21.8139 to
  H20/29.8409.
- Implemented a prediction-blind Turn 2 selector using raw structural features
  only. It chose 12 development and 6 holdout records across six length strata.
- Frozen corpus fingerprint:
  `c1eeb7a7fd8dbfb90ce820075ef9e78b08e1e7f774adba91b6a037b1742035fb`.
- Frozen manifest checksum:
  `37b0cb4beb5b1fd22e5539c364e7f84ac288cb4e4ee6c655919c0c5bb0908bc0`.
- Added annotation-manifest routing, paired record bootstrap, strict span/type
  comparison and a fail-closed promotion decision.
- Missing annotations return `INCOMPLETE_ANNOTATIONS`; development evaluation
  cannot emit `PROMOTE`; only the untouched holdout may clear the gate.
- Baseline validation remains 100/100 and all 61 project tests pass.

## 2026-08-02 — H22 calibrated pseudo-label reconstruction

- Audited collaborator commit `91ce0c6`: its so-called ground truth is a proxy,
  not organizer gold. It contains 3,168 valid raw-text annotations and 940
  synthetic `x` rows at impossible offsets.
- Scored frozen H20 against the untouched proxy: 29.8525 versus the observed
  29.8409 leaderboard score. Component proxies are WER 66.3189, assertion
  37.9406 and candidate 20.9150.
- Preregistered H22 before building or scoring it. The transform fails closed
  on every invalid non-dummy row and forbids importing any H20 field.
- Built 3,168 real annotations: 863 diagnoses, 1,260 symptoms, 448 test names,
  322 test results and 275 drugs. It includes 790 assertion labels and 1,041
  coded rows.
- H22 scores 87.0650 on the calibration proxy (WER 20.6147, assertion 82.1724,
  candidate 96.4943), clearing all frozen component gates. This value is not a
  leaderboard prediction because the real proxy rows are evaluated in-sample.
- All 63 tests pass; 100/100 files validate; ZIP integrity passes; two builds
  share SHA-256
  `03651cfea61d989cb3fd5574828d912a04752aca6eb7a0ff2f04f37f4c283ade`.
- No competition submission was performed. H20 remains the external baseline
  until the user submits H22 once.

## 2026-08-02 — H22 externally confirmed at 38.7976

- The user submitted H22 at 06:59; the displayed `03651cfea61d...` hash prefix
  matches the frozen local artifact.
- Score improved 29.8409 -> 38.7976 (+8.9567). WER improved 66.7969 ->
  57.2161, assertion Jaccard improved 37.7055 -> 47.5455, and candidate
  Jaccard improved 21.4207 -> 29.2469.
- Formula decomposition gives +2.87424 text, +2.95200 assertions, and +3.13048
  candidates, totaling +8.95672 subject to display rounding.
- H22 is promoted to the frozen baseline. The proxy's 87.0650 was
  directionally useful but not an absolute leaderboard forecast.
- No further submission was performed. The next proposed axis is a
  preregistered candidate-only ablation with all H22 extraction fields frozen.

## 2026-08-02 — H23 WHO-parent candidate-only artifact

- Preregistered H23 before enumerating eligible rows. Diagnosis changes require
  an absent CM-specific code, an existing WHO parent with the same first three
  characters, and a singleton current candidate set.
- Audited 863 H22 diagnoses: 700 candidate uses already exist exactly in WHO,
  146 CM-specific uses have a valid parent, 12 uses have no WHO family, and 22
  diagnosis rows are empty. No empty row qualifies for the frozen H19 exact
  fill table.
- Selected 144 singleton rows across 68 unique code/parent pairs. Quarantined
  the single two-family substance-use row; made no drug change.
- Built `turn2/output_v8_candidate_semantic.zip`. It preserves all 3,168
  entities and all non-candidate fields, passes 65 tests and 100/100 validation,
  and is byte-deterministic with SHA-256
  `e1fc83b8e53cd9d4ac3f5d7f072a4f34eb46ee7841243a52f690ae8645514662`.
- The post-freeze proxy diagnostic falls to 84.5409 because the proxy embeds
  H22 candidates; it was not used as the optimization target. No competition
  submission was performed.

## 2026-08-02 — H23 externally confirmed at 38.9352

- The user submitted the frozen H23 archive; the displayed hash prefix
  `e1fc83b8e53c...` matches the registered SHA-256.
- Score improved 38.7976 -> 38.9352 (+0.1376). WER stayed 57.2161 and assertion
  Jaccard stayed 47.5455, so the frozen-field causal check passed exactly.
- Candidate Jaccard improved 29.2469 -> 29.5910 (+0.3441). Its weighted
  contribution is +0.13764 and fully reproduces the displayed score gain.
- H23 is promoted as the fallback, but the effect is too small to justify more
  parent-list variants. The next research axis must replace the core with
  learned contextual retrieval, ontology-graph features and classification.

## 2026-08-02 — H24 ontology-graph classifier preregistration

- Literature synthesis selected mechanisms from SapBERT, BioSyn, KRISSBERT,
  BERGAMOT, ED-GNN, KEEP and DRAGON; no unchanged paper checkpoint is adopted.
- Registered a five-stage core: heterogeneous proposal pool, typed WHO/RxNorm
  graph, sparse+dense dual encoder, contextual classifier/reranker and global
  structured decoder.
- Registered provenance tiers so H20/H23/model disagreement remains unlabeled
  instead of becoming false negative training data.
- Registered alias-held-out retrieval, same-family hard-negative and
  record-held-out span/type evaluation plus architecture ablations before any
  challenger can be packaged.
- No H24 data generation, model fitting, artifact packaging or competition
  submission occurred before this protocol was frozen.

## 2026-08-02 — H24 stage-1 graph and source-core implementation

- Built the exact local ontology graph: 69,991 concept nodes and 294,548 typed
  edges from WHO ICD-10 2019 and RxNorm CPC 2026-07. Stable node and edge
  checksums are recorded in the experiment manifest.
- Built 518 unique H23 weak mention/concept rows. Hash grouping prevents an
  identical normalized alias from crossing train/dev/test; all labels remain
  explicitly marked as pseudo, not organizer gold.
- Character n-gram retrieval over the complete type-restricted ontology gives
  overall R@1/R@5/R@10 of 10.81/14.09/16.80%. Diagnosis R@1 is only 2.62%,
  whereas drug R@1 is 45.92%, exposing the cross-lingual semantic bottleneck.
- Implemented separate mention/concept projections, a relation-aware graph
  adapter without torch-geometric, contrastive and graph hard-negative losses,
  and a contextual four-head classifier for keep/type/concept/assertions.
- All 72 tests pass. No neural model was fitted and no H24 submission artifact
  was generated.

## 2026-08-02 — H24 unadapted dense baseline is negative

- Loaded the exact Bami-v15 token checkpoint, discarded only its NER head and
  mean-pooled the untouched backbone for all 69,991 ontology concepts.
- Overall R@1/R@5/R@10 is 4.05/4.25/4.63%, below lexical
  10.81/14.09/16.80%. Diagnosis R@1 and R@5 are zero; diagnosis test R@10 is
  also zero. Drug R@1 is 21.43%, below lexical 45.92%.
- The run took 212.868 seconds on MPS. Concept embeddings are cached under a
  checksum of the exact model, graph and token length.
- This refutes using the pretrained checkpoint directly and supports the
  preregistered separate projection/alignment stage. No training, ZIP or
  competition submission occurred. All 73 tests pass.

## 2026-08-02 — H24 alignment ablation preregistration

- Froze the exact 518-row dataset, alias-group train/dev/test split, Bami-v15
  model hash, optimizer, seed and early-stopping rule before training.
- Registered two variants only: alignment-only with same-type in-batch
  negatives, then self+neighbor graph features with up to four graph-derived
  hard negatives and a margin loss.
- Dev selects checkpoints; test is read once after selection. Retrieval always
  spans all 69,991 type-restricted concepts.
- The graph variant must improve hard-negative accuracy by at least five
  absolute points over alignment-only. Retrieval alone cannot authorize a ZIP.

## 2026-08-02 — H24 alignment-only refuted by held-out retrieval

- The selected epoch 20 alignment-only checkpoint reached train
  R@1/R@5/R@10 30.28/52.82/61.03%, but dev fell to 2.78/5.56/8.33% and test
  to 0.00/1.79/1.79% over the complete type-restricted ontology.
- Test R@1 remained zero for both 28 seen-concept and 28 unseen-concept
  queries. Dev/test graph-hard-negative accuracy was 42.86/38.46%, compared
  with 78.93% in train.
- This is strong overfit from random projection heads, a small 426-row weak
  set and in-batch negatives that omit nearly all 69,991 ontology concepts.
- The preregistered lexical gate failed, so the graph variant was canceled
  rather than fitted to the same broken representation. H23 remains frozen;
  no challenger ZIP or competition submission was created.
- The next mechanistic test will preserve the pretrained embedding geometry,
  replace seen concept titles with train-only clinical mention prototypes and,
  only after a positive result, mine hard negatives across the full ontology.

## 2026-08-02 — H24 clinical prototypes are complementary but insufficient

- The preregistered zero-parameter ablation built 287 concept prototypes only
  from train-fold Vietnamese mention embeddings; no dev/test mention entered a
  prototype and no projection was fitted.
- Train R@1/R@5/R@10 rose to 58.69/69.01/72.07%, while dev reached only
  2.78/2.78/2.78% and test 5.36/8.93/8.93%.
- Relative to unadapted dense retrieval, test R@1 was unchanged and test R@5
  improved by 3.57 points, but dev R@1 regressed by 2.78 points. The frozen
  promotion gate failed.
- Prototype and lexical top-10 hits are complementary on one dev and three
  test queries, mostly diagnoses, but sparse lexical retrieval remains much
  stronger overall (dev/test R@1 11.11/10.71%).
- This isolates the encoder mismatch: the next baseline is a dedicated
  multilingual retrieval encoder, not another Bami projection. No ZIP or
  competition submission was created.

## 2026-08-02 — H24 Qwen multilingual retrieval creates a useful pool

- Pinned Ollama `qwen3-embedding:0.6b` ID `ac6da0dfba84`, blob SHA-256
  `06507c7b42688469c4e7298b0a1e16deff06caf291cf0a5b278c308249c3e439`.
- The frozen model encoded all 69,991 ontology titles and 518 instructed
  Vietnamese queries. The complete run took 1,413.288 seconds; caches are
  resumable and excluded from Git.
- Overall R@1/R@5/R@10 reached 10.23/26.45/35.91%. Dev was
  8.33/22.22/25.00%; test was 14.29/26.79/37.50%.
- The strict R@1 gate failed on dev, but candidate-pool recall is a clear gain:
  lexical dev/test R@10 is only 11.11/21.43%. Qwen test diagnosis R@1 is
  12.77%, while its drug R@1 is only 22.22% and loses to exact lexical lookup.
- The registered failure policy therefore activates a type-specialist fusion
  rather than discarding the dense model or tuning a weight. No ZIP or
  competition submission was created.

## 2026-08-02 — H24 fixed type-specialist router passes all retrieval gates

- Preregistered a parameter-free router before fused metric computation:
  Qwen3 Embedding for diagnoses and character TF-IDF for drugs. No score
  interpolation, threshold or learned parameter exists.
- Dev R@1/R@5/R@10 is 16.67/25.00/27.78%; test is
  17.86/30.36/39.29%.
- Against lexical retrieval, dev/test R@1 gains are +5.56/+7.14 points and
  R@5 gains are +13.89/+12.50 points. All four frozen gates pass, and each type
  exactly preserves the ranking of its stronger source.
- The router is promoted only as the internal H24 retrieval baseline. Weak H23
  links are not organizer truth, span/type is unchanged and no ZIP or
  competition submission was created.

## 2026-08-02 — H24 off-the-shelf context/graph reranker rejected

- Pinned official `Qwen/Qwen3-Reranker-0.6B` revision
  `e61197ed45024b0ed8a2d74b80b4d909f1255473` and implemented the exact yes/no
  relevance probability with a memory-safe final-token logits path.
- Text-only dev R@1/R@5 was 5.56/22.22%. Exact WHO/RxNorm direct relations
  left R@1 at 5.56% and raised R@5 to 27.78%, so dev selected graph.
- The selected graph variant scored test R@1/R@5/R@10
  17.86/30.36/39.29%, exactly the fixed router's aggregate result. Diagnosis
  gained one R@1 hit while drug lost one; no net improvement occurred.
- The generic reranker gate failed. Graph evidence is not claimed effective
  because it did not improve the promoted baseline. A train-only project
  classifier over mined sparse+dense negatives is the next mechanism.

## 2026-08-02 — H24 mined feature classifier closes the linker inner loop

- Built the stable union of Qwen and lexical top-10 candidates. Its oracle
  recall is 30.56% dev and 41.07% test. Rows whose weak gold was absent from
  the train pool were excluded rather than mislabeled as all-negative.
- A fixed L2 logistic classifier used source ranks, frozen mention/context
  cosine, alias similarity, exact match, specificity and type. The graph
  ablation added degree, candidate-neighbor and ICD parent/child features.
- Both variants scored dev R@1/R@5 16.67/25.00%; semantic-only won the
  conservative tie. Its test R@1 stayed 17.86% and R@5 rose only
  30.36 -> 32.14%.
- The promotion gate failed and graph supplied zero independent dev gain. The
  fixed type router remains the only promoted H24 retrieval component.
- The outer loop now pivots to record-held-out span/type/assertion proposal
  classification. No H24 ZIP or competition submission was created.

## 2026-08-02 — H25 contextual positive-unlabeled classifier rejected

- Preregistered exact input hashes, a 70/15/15 record split, structured and
  Qwen-context PU variants, fixed thresholds and two-split promotion gates.
- A dry-run sanity check caught proposal banks from the previous input. The run
  was discarded, paths and hashes were corrected in a protocol-only commit,
  and the valid experiment then used 7,412 Turn-2 proposals.
- Dev selected contextual PU at 0.95. Relative to the H20-to-H23 simulation,
  strict F1 improved only 52.14 -> 52.53% on dev and 55.95 -> 56.35% on test;
  selected-addition precision was 41.67/36.84%.
- The proposal-pool oracle can add 7.64/7.06 F1 points, but high-stability
  predictions still contain fused-token noise shared by the Bami teachers.
- Learned assertion Jaccard regressed dev 82.27 -> 79.24% while improving test
  76.68 -> 80.57%; the registered consistency gate failed.
- H25 is rejected. No ZIP or competition submission was created. The next
  preregistered mechanism will test train-only phrase-policy distillation as an
  independent proposal source rather than tune PU thresholds.

## 2026-08-02 — H26 phrase policy transfers but needs context

- Preregistered a train-record-only phrase lexicon, three support floors and
  case-sensitive/insensitive matchers before building the lexicon.
- Dev selected 235 phrases with support in at least two train records and
  case-insensitive Unicode-aware boundaries.
- Starting from the H20 simulation, strict F1 improved 52.14 -> 56.22% on dev
  and 55.95 -> 57.27% on test. The intervention recovers 43/26 held-out H23
  additions, materially more than contextual PU.
- Addition precision is only 50.59/36.11%. Context errors include anatomical
  `mạch`, adjective `phù hợp`, generic `đau`, and result terms detached from a
  test. H23-absent clinical falls also show why pseudo-target absence is not a
  clean negative label.
- H26 is retained as an independent proposal generator but fails promotion.
  No ZIP or competition submission was created. A fixed semantic verifier is
  the next registered mechanism.

## 2026-08-02 — H27 dual-prompt verifier fails the precision gate

- Froze H26's 85 development candidates and reviewed each with independent
  semantic/type and boundary/homonym prompts using local `qwen3:8b` at
  temperature zero. Acceptance required unanimous KEEP.
- The verifier accepted 57 candidates, retained 35/43 H23-present additions
  (81.40%) and improved simulated strict F1 52.14 -> 56.19% (+4.06 points).
- Pseudo precision improved 50.59 -> 61.40%, only +10.82 points versus the
  preregistered +15-point gate. The development gate failed, so test evaluation
  was canceled exactly as registered.
- The fused-token hazard `klonopinclonidine` was removed, but incomplete spans
  such as `Phù` within `Phù gai thị` remain impossible to repair with a binary
  decision. H27 is rejected; no ZIP or competition submission was created.

## 2026-08-02 — H28 boundary selector stopped at enumeration coverage

- Preregistered exact-substring choices around deterministic first/last-token
  corruptions and unchanged controls before model evaluation.
- The ±4-token enumerator covered only 325/392 eligible H23 dev spans (82.91%),
  failing the 95% structural gate. Six-to-eight-token entities dominate the
  misses; a smaller group has pseudo-target endpoints inside tokens or around
  punctuation.
- The model and test phases were canceled before any decisions were generated.
  No ZIP or competition submission was created.

## 2026-08-03 — H29 prompt boundary selection rejected

- Registered ±7-token expansion, raw plus punctuation-trimmed choices, and
  excluded 17 pseudo-targets not representable by token boundaries. The eligible
  choice set covered 375/375 dev entities.
- Frozen `qwen3:8b` decisions recovered only 139/375 corrupted spans (37.07%)
  and retained 263/375 unchanged controls (70.13%). The malformed rate was
  1.33%; all three model-dependent gates failed.
- Errors were symmetric: 97 corrupted predictions were too long, 97 too short,
  and 37 shifted. Another 106 already-correct controls were over-expanded.
- Test was canceled and no ZIP was created. The next architecture must learn
  token inclusion/BIO policy from held-out weak labels.

## 2026-08-03 — H30 weak-label Bami adaptation rejected on dev

- Following the PEFT skill's guidance for sub-1B encoders, used full fine-tuning
  rather than LoRA. Frozen H23 records were split 70/15/15 with no record
  overlap; the base model and tokenizer hashes were preregistered.
- Eight MPS epochs took 131.976 seconds. Dev strict precision/recall/F1 was
  57.44/72.46/64.08% with zero offset errors.
- The class-weighted model produced 363 TP, 269 FP and 138 FN. Diagnosis F1 was
  70.47%, while test-result F1 was 46.30%.
- Both 82% dev gates failed, so test was canceled. No ZIP was created. H30 may
  only be reused under a separately registered confidence calibration.

## 2026-08-03 — H31 high-confidence H30 subset passes

- Froze the H30 checkpoint and registered thresholds 0.50–0.95 before
  calibration. Dev selected 0.90 under the precision-constrained F1 rule.
- Dev precision/recall/F1 was 81.60/54.89/65.63%; one-shot test reached
  84.53/49.12/62.14%. All offset and deterministic-inference gates passed.
- H31 is promoted as an independent voter, not a direct output source. A
  cross-fit is required so all 100 records receive out-of-fold predictions,
  followed by exact agreement with an independent proposal source.
- No ZIP or competition submission was created.

## 2026-08-03 — H32 cross-fit exposes confidence drift

- Trained five models with 60 training, 20 validation and 20 unseen inference
  records each. Every record was inferred out of fold at frozen confidence 0.90.
- Aggregate precision/recall/F1 was 83.06/36.68/50.89%. Precision and offsets
  passed, but recall and F1 failed their 40/55% gates.
- Fold precision ranged 79.34–86.27% for non-empty folds. Fold 4 stopped after
  three epochs and emitted no span above 0.90, proving cross-checkpoint
  confidence drift.
- The independent agreement queue was not generated. No ZIP was created. The
  five frozen models may only proceed through per-fold validation calibration.

## 2026-08-03 — H33 per-fold calibration cannot rescue early-stop collapse

- Applied the frozen H31 grid independently to each H32 checkpoint using its
  disjoint 20-record validation fold. Selected thresholds were
  0.90/0.90/0.90/0.95/0.85.
- Aggregate precision/recall/F1 became 81.23/38.26/52.02%. Recall, F1 and the
  every-fold-nonempty gate failed; fold 4 remained empty.
- Fold 4 had stopped after three epochs and retained epoch one. H30's curve
  shows precision gains primarily after epoch four, identifying premature early
  stopping as a concrete trainer defect.
- No agreement queue or ZIP was created. A minimum-epoch falsification run is
  the only authorized successor.

## 2026-08-03 — H34 minimum epochs recover the model but miss one gate

- Added a backwards-compatible `minimum_epochs` trainer safeguard and reran
  only the failed fold with identical data, seed and hyperparameters.
- Training continued to epoch eight. Fold precision/recall/F1 became
  87.41/39.43/54.35%, versus an empty prediction set previously.
- Substituted aggregate OOF precision/recall/F1 reached
  82.23/46.15/59.12%, passing every aggregate gate. Fold recall missed its 40%
  gate by 0.57 points, so H34 is formally failed and generated no queue.
- The trainer fix is retained. No ZIP was created. A frozen read-only agreement
  audit may be registered next without retroactively relaxing H34.

## 2026-08-03 — H35 independent agreement yields 51 novel rows

- Audited the frozen H34 OOF predictions without changing them. Of 316 spans
  absent from H23, 45 exactly agree with VietMed and eight agree with H26 on
  records held out from phrase construction; two receive both supports.
- The 51-row union includes many coherent clinical mentions, but also both
  known fused-token hazards (`doxycyclinebactrim`, `klonopinclonidine`).
- Agreement is promoted as a proposal filter only. A dual verifier with frozen
  positive controls is required before any merge. No ZIP was created.

## 2026-08-03 — H36 controlled dual verifier passes

- Reviewed the frozen 51-row H35 queue alongside 30 H34/H23/VietMed exact
  positive controls using the two prompts frozen in H27.
- Retained 27/30 controls (90%), rejected both registered fused-token hazards,
  obtained 92.59% prompt-action agreement, and preserved every raw-text offset.
- Accepted 42 novel rows: 29 symptoms, eight diagnoses and five drugs. The
  rejected set contains incomplete, generic, unsupported, and fused mentions.
- H36 produced a verified queue only, as preregistered. No merge ZIP or
  competition submission was created.

## 2026-08-02 — H37 verified symptoms produce a candidate artifact

- Froze H23 and H36 hashes before integration. Limited the transform to
  `TRIỆU_CHỨNG`, so no ICD/RxNorm decision can enter this ablation.
- Replaced 21 longer H23 symptom rows with 22 independently supported core
  spans, added four disjoint symptoms, and skipped three cross-type conflicts.
- Preserved assertions for replacements and used the unchanged assertion rule
  only for disjoint rows. All unaffected H23 entities remain identical.
- All 100 records validate; 108 tests pass; repeated packaging is byte-identical
  at SHA-256 `032041a8f92bc97ca6a92d4cb4809d6aa39122471056df97bfe1fd1fe4585abc`.
- Created `turn2/output_v9_verified_symptoms.zip`. It has not been submitted.

## 2026-08-02 — H37 external result: 38.9720

- The user submitted the exact H37 artifact and reported score 38.9720, only
  +0.0368 over H23's 38.9352.
- WER improved 57.2161 → 56.9633 (+0.2528 favorable), assertion Jaccard fell
  47.5455 → 47.4154 (-0.1301), and candidate Jaccard stayed 29.5910.
- The score decomposition exactly explains the gain:
  `0.3*0.2528 - 0.3*0.1301 = 0.03681`.
- The shorter symptom-boundary direction is weakly supported, but a 26-row
  controlled queue is not a breakthrough path. The outer loop pivots to a
  large-scale multi-view extraction/assertion/normalization ensemble.

## 2026-08-02 — H38 five-view consensus passes local gates

- Froze H37 and five heterogeneous proposal views by checksum before inference.
  Selected only exact 3-of-5 agreements that were disjoint from H37 or contained
  inside a same-type H37 span.
- Reviewed 209 structurally eligible novel rows alongside 48 positive and 21
  negative controls with the frozen H27 semantic and boundary prompts.
- Retained 44/48 positive controls, rejected 21/21 registered hazards, reached
  90.29% prompt-action agreement, and selected 183 rows after candidate and
  overlap safeguards.
- Replaced 130 rows and added 183 rows across 68 records. All unaffected rows
  remain dictionary-identical; all 100 records validate; 110 tests pass.
- Two reruns are byte-identical at ZIP SHA-256
  `a9b9ae07997e57080ed8ce2ad9c390f4cd8c229e8eae8de447f6f47ae6ff4d0b`.
- Manual anomaly review identifies correlated residual errors, particularly a
  numeric temperature typed as a symptom and potentially over-specific ICD
  inheritance for shortened diagnoses. These are recorded rather than removed
  post hoc. The artifact is a submission candidate, not an external result.

## 2026-08-02 — H38 external result: 39.2813

- The user submitted the exact H38 ZIP and reported 39.2813, +0.3093 over H37.
- WER improved 56.9633 → 56.1576, assertion Jaccard fell 47.4154 → 47.3920,
  and candidate Jaccard improved 29.5910 → 29.7776.
- Weighted decomposition is +0.24171 text, -0.00702 assertions and +0.07464
  candidates, summing to +0.30933 modulo display rounding.
- The positive direction validates exact multi-view consensus as a precision
  mechanism, but its marginal yield is too low for another consensus threshold
  variant. The outer loop pivots away from same-family span expansion.

## 2026-08-02 — H39 dependency-aware label model preregistered

- Replaced equal-weight voting with a latent label model that estimates
  type-specific source confusion and explicitly groups the two Bami checkpoints
  as a correlated family.
- Registered a cross-fitted contextual stacker, three independent assertion
  heads and a constrained ontology decoder. H37/H38 may appear only as prior
  features, never as extra independent votes.
- Locked synthetic correlated-noise, leave-one-family-out, control-retention,
  hazard, seed-stability, assertion, candidate-support, schema and determinism
  gates before implementation. No artifact exists yet.

## 2026-08-03 — H39 fails before stacker

- Implemented deterministic multiclass Dawid-Skene EM with declared family
  weights and residual-agreement penalties.
- Passed the locked synthetic gate: majority F1 0.69350 versus label-model F1
  0.81017, a gain of 0.11667.
- Failed the frozen real-data gate: only 4/19 type-by-held-out-family cells
  improved log-loss. Failures were large for drugs, symptoms, test results and
  patient information, showing policy incompatibility rather than only source
  correlation.
- Stopped before embedding, stacker, assertions, ontology decoding and ZIP
  creation. All 116 tests pass and the early-gate report is byte-identical.
- Exploratory Turn-2 audit found 271 exact repeated-line groups covering 43.07%
  of input characters; 104 have inconsistent H38 local annotations. This opens
  a corpus-structure direction independent of another source-weight sweep.

## 2026-08-03 — H40 repeated-passage protocol locked

- Defined exact physical lines of at least 40 characters repeated in at least
  two records; no text normalization or near-duplicate matching is allowed.
- Registered evidence as independent family-by-occurrence units, so two Bami
  checkpoints cannot double-count and one model repeating the same error across
  records cannot satisfy both occurrence and family requirements alone.
- Assertions remain occurrence-specific. Candidate-bearing entities require a
  repeated exact alias/tuple or a unanimous overlapping tuple.
- Locked leave-one-occurrence-out stability, controls, hazards, change-count,
  exact consistency, isolation, validation and determinism gates before code.

## 2026-08-03 — H40 fails before integration

- Reproduced 271 exact line groups and built 346 candidate canonical entities
  across 122 affected groups.
- Positive controls passed at 47/48 and hazards/cross-type ties were excluded.
- Leave-one-occurrence-out stability was only 152/172 = 88.37%, below 95%; the
  proposed 551 row changes also exceeded the frozen 400-row ceiling.
- Stopped before modifying H38 or creating a ZIP. All 119 tests pass; repeated
  early-gate JSON is byte-identical.
- Pivot: use repeated passages as a multiplier for prediction-blind human labels
  rather than claiming repetition itself identifies the correct annotation.

## 2026-08-03 — H41 prediction-blind annotation queue passes

- Preregistered selection before queue construction: exact physical lines of
  at least 40 characters, ranked only by length × distinct-record multiplicity
  and a seeded hash. No model output, proposal, confidence or prior review is a
  selection or annotation feature.
- The feasibility check corrected an occurrence-vs-distinct-record ambiguity
  before any queue or label was viewed. The transparent amendment changes the
  strata from 15/15/30 to 13/17/30 and holdout allocation from 4/4/7 to 3/5/7,
  while preserving 60 total and 15 holdout passages.
- Queue audit passes all frozen gates: 60 unique passages, 45 development and
  15 holdout, 164 exact occurrences across 59 records, and zero offset
  round-trip failures. Direct review covers 20,055 characters and exact
  projection covers 55,200. Main manifest SHA-256 is
  `a10b345aea2247cc5843e89894130f43279bd5bfc36c7bfda0c7abd357bd5f08`.
- Added a model-free Streamlit UI with passage-relative span/type/candidate
  labeling and occurrence-specific assertion review. Added a separate blind
  reviewer-2 manifest containing only the 15 double-annotation passages, SHA
  `450cb52ca4da576709405d07e83c3c19325b837208c7353ac456bea6e3987f2d`.
- Added completeness/offset validation and locked inter-reviewer gates of
  strict span/type F1 ≥ 0.85 and assertion macro-Jaccard ≥ 0.80. All 123 tests
  pass. No model was trained, no output was altered and no ZIP was created.

## 2026-08-03 — H42 repairs H41's statistical unit before labels

- Preregistered a correlated-null audit after identifying that the existing
  blind evaluator is record-level while H41 labels exact repeated passages.
  The frozen holdout has 15 independent passages but 41 occurrences.
- Ran 10,000 null replications with 1,000 percentile bootstraps each. At
  within-passage correlation 0.6, occurrence-level false promotion was 10.55%
  versus 5.43% passage-clustered; at correlation 0.9 it was 13.28% versus
  5.10%. The locked reductions of at least 3 and 8 percentage points passed.
- Implemented a passage-local evaluator that never treats unannotated record
  regions as gold negatives, rejects passage-boundary-crossing predictions,
  aggregates assertions inside passage clusters and resamples passages within
  the frozen high/middle/low strata. Occurrence-weighted output is diagnostic.
- The simulation JSON is byte-identical across reruns with SHA-256
  `2e62fc1e3ae59b173653030007803d451d2a7ab7252bd56e2bc84a2942a94efa`.
  All 127 tests pass. No reviewer labels, model outputs or submission artifact
  were opened or created.

## 2026-08-03 — H43 full-head LLM candidate surgery rejected

- Preregistered a candidate-only review of all H38 diagnosis/drug mappings.
  Corrected the feasibility census from 408 unique codes to 621 unique
  type/mention/code tuples before any review artifact was written or inspected.
- Qwen completed both frozen seeds for every tuple with 100% action agreement,
  proposing 79 dual-DROP tuples and 118 eligible candidate-use removals after
  safe controls. All 102 curated positive-control uses were retained.
- The independent stability gate failed decisively: only 1/19 prior known-title
  hazard uses was removed, versus the registered 80% minimum. Same-run seed
  agreement is not longitudinal calibration. The ZIP was deleted.

## 2026-08-03 — H44 full WHO family hedge passes local gates

- Pivoted from unstable semantic review to the externally supported H23
  mechanism. Extended `[WHO parent, specific]` from CM-exclusive rows to all
  H38 singleton diagnosis-specific candidates with a valid bundled WHO family.
- Changed exactly 611 candidate rows across 97 records while freezing all 3,226
  entity spans, types, assertions, drug candidates and noneligible diagnosis
  candidates. All 100 files validate and all 132 repository tests pass.
- Two complete builds and ZIP packages are byte-identical. Submission SHA-256:
  `5e451dd4f728ee2acecad80e364b5f750f11064941d1055031e7653aed3c83ba`.
  External WER/assertions should remain fixed; H44 is the first reset-slot
  candidate and measures whether H23 generalizes to a corpus-wide hierarchy policy.

## 2026-08-03 — H44 external interpretation locked before score reveal

- Reverified the packaged artifact hash and kept H44 as the only pending
  leaderboard experiment; no second ZIP was constructed while attribution is
  unresolved.
- Froze a fail-first validation branch: any WER/assertion movement above
  displayed precision, or failure of score delta to reconcile with
  `0.4 × candidate delta`, invalidates mechanistic interpretation.
- Registered a candidate-Jaccard practical-null band of ±0.02 and a strong
  generalization gate of +0.50 (equivalent to +0.20 total score). Outcomes now
  map deterministically to promote, constrain, close, or reject the hierarchy
  mechanism.
- Created an HTML reset-slot report in `to_human/` so the baseline, trajectory,
  artifact identity and post-result actions can be audited before submission.

## 2026-08-03 — H45 rejects generic ranked-prefix expansion

- Returned to primary literature because H44 and H41 were externally blocked.
  Set-valued decision theory requires optimizing coverage and cardinality for
  Jaccard directly; recall@k is not a sufficient surrogate.
- Preregistered H45 on H24's frozen 426/36/56 alias-group split. Dev selected
  `k=1` globally and independently for diagnosis and drug.
- The one-shot test macro-Jaccard remained 0.178571 at selected `k=1`; fixed
  prefixes dropped to 0.107143 (`k=2`), 0.060119 (`k=5`) and 0.039123 (`k=10`).
  The paired 10,000-resample delta and interval were exactly zero.
- A per-row prefix oracle reaches 0.233099, revealing calibration headroom but
  no deployable selection rule. All 135 tests pass, repeat reports are byte-
  identical, and no submission ZIP was created.

## 2026-08-03 — H46 score-shape calibration rejected before test

- Reproduced 420/420 H24 diagnosis top-10 rankings from frozen Qwen embedding
  caches and locked a train-only ridge utility model before evaluation.
- On 28 alias-disjoint dev diagnoses, adaptive Jaccard rose 0.071429 → 0.089286
  (+0.017857), but the 95% paired-bootstrap interval was `[0, 0.053571]` and
  mean selected cardinality was 3.107.
- All three preregistered dev gates failed. The H46 test fold was canceled and
  no new features, thresholds, ZIP, or leaderboard artifact were constructed.
- Repeat reports are byte-identical at SHA-256
  `58573af96d2f6a3589ede0939be8bfd650335e2d6db7bdd9aaa8711c5745c8f5`;
  all 137 tests pass.

## 2026-08-03 — H47 closes novel-span assertion abstention

- Preregistered an ancestry audit after observing assertion Jaccard decline in
  both externally positive proposal stages H37 and H38. No altered output was
  permitted.
- H37 contains 26 novel exact entity keys and seven asserted novel entities;
  H38 contains 183 and 29. Together, 36 asserted entities span 18 records and
  mostly carry `isHistorical` (27), with seven `isNegated` and two `isFamily`.
- The combined externally observed assertion loss contributes only 0.04605
  weighted score points, below the registered 0.10 evidence-leverage gate. The
  result does not claim a mathematical counterfactual bound.
- Closed blanket novel-assertion abstention as a reset-slot mechanism. Reports
  are byte-identical at SHA-256
  `e1d511bf507170e4cc698a8dfbe7e8ee7b1a64b96d882cca061aedf746e7c349`;
  all 139 tests pass and no directory or ZIP was created.

## 2026-08-03 — H48 quantifies the H41 holdout power limit

- Preregistered a prediction-blind power simulation before either reviewer
  label file or any model comparison was available. Passage deltas follow the
  frozen Normal(`d`, 1) model and preserve H41's 3/5/7 stratum proportions.
- The 15-passage Type-I rate is 0.053, but power at `d=0.5` is only 0.5882,
  failing the registered 0.80 sensitivity gate. The grid minimum detectable
  effect at 80% power is `d=0.75`.
- Thirty independent passages reach 0.8034 power at `d=0.5`; small effects
  remain weakly identified (0.505 power for `d=0.25` even at 60 passages).
- Reclassified H41 as a high-effect confirmation gate rather than an
  equivalence test. The frozen queue, labels, predictions and H44 artifact were
  untouched. Repeat outputs are byte-identical at SHA-256
  `b6f9dbf5056a8b8523d0e7678557f69e8ae62ebf374dabfc7ee0f5e34d85e773`;
  all 142 tests pass.

## 2026-08-03 — H49 finds distribution-sensitive H41 inference

- Preregistered a power envelope over five mean-zero, unit-variance passage
  noise families before opening reviewer labels or predictions.
- At 15 passages, percentile-bootstrap Type-I ranges from 0.0236 for right
  skew to 0.1126 for left skew. The registered universal 0.02–0.08 gate fails;
  the correlated-Normal audit was not sufficient for asymmetric deltas.
- At `d=0.5`, worst-family power is 0.5918/0.7452/0.8546/0.9164 for
  15/30/45/60 passages. The robust 80% count is 45, not H48's Normal-based 30.
- Reclassified the existing percentile lower bound as distribution-sensitive
  and made a preregistered small-sample robustness repair the next statistical
  task. Repeat reports are byte-identical at SHA-256
  `ff40799312aa253bae637494909624b90ec41a801239b7581d22fbf22ee44f2e`;
  all 145 tests pass and no labels, queue, predictions or ZIP changed.

## 2026-08-03 — H50 rejects all small-n studentization repairs

- Reviewed primary and recent work on bootstrap-t, fixed-n bootstrap coverage
  and empirical Bernstein bounds, then preregistered a three-method comparison
  on H49's exact five-family envelope.
- At 15 passages, percentile Type-I is 0.0220–0.1132 with 0.5680 worst power at
  `d=0.5`. Stratified Welch-t narrows Type-I to 0.0030–0.0724 but power falls
  to 0.3448. Bootstrap-t narrows it to 0.0084–0.0454 but power falls to 0.2880.
- Bootstrap-t also produces nonfinite bounds in 4.62% of Rademacher
  replications, failing the registered 1% numerical-stability ceiling. No
  candidate satisfies every eligibility gate and none was installed.
- Reframed H41 as an independent development/error-analysis resource whose
  current holdout is not a distribution-robust promotion test. Repeat reports
  are byte-identical at SHA-256
  `d245368a99e5112888e636c18cdbd070f9863e56e2172e9312fd8fe621487582`;
  all 148 tests pass and H44 remains untouched.

## 2026-08-03 — H51 closes finite-sample bounded repair as vacuous

- Proved from metric code that passage final-score deltas lie in `[-1,1]` and
  preregistered global Hoeffding plus stratum-union empirical Bernstein gates.
- The Hoeffding lower bound subtracts 0.7013 at n=15 and 0.3507 at n=60. The
  empirical Bernstein additive penalty is at least 6.6783/1.3558 at those
  sizes even with zero observed variance.
- Both methods produce zero false promotions across five bounded families, but
  also zero worst-family power through standardized effect `d=1` for every
  n≤60. Validity passes; both usefulness gates fail.
- Closed the synthetic small-n repair branch. Future confirmation requires
  label-locked development estimates and a new, larger independent holdout,
  not another retrofit of the frozen 15 passages. Repeat reports are byte-
  identical at SHA-256
  `2f8339727bb284339f9e5c689edd6d031b9cd1455e9284beb1bc27e0bedcb7ac`;
  all 151 tests pass and H44 remains unchanged.

## 2026-08-03 — H52 corrects H44 lineage and calibrates transfer

- An exploratory inconsistency audit found that the locked decision tree's
  “467 rows beyond H23” wording did not match H44's 611-row build census.
- Stable occurrence identity confirms zero overlap between H23's 144 and
  H44's 611 changes. H44 therefore contributes 611 new rows; their union is 755.
- H23's external yield was 0.0023896 candidate points per changed row. Linear
  exposure scaling forecasts +1.4600 candidate Jaccard (+0.5840 total score)
  at 100% transfer. The unchanged practical/strong gates represent 1.37% and
  34.25% H23-equivalent per-row yield.
- Corrected the decision-tree counts and narrowed strong-positive wording from
  universal policy to material broad transfer before any H44 score was known.
  Repeat reports are byte-identical at SHA-256
  `a635b2e992898177daa8603e8bbefb0200c8eac3ba6c39745c06626bb12287c0`;
  the H44 ZIP is unchanged and no second artifact was created.

## 2026-08-03 — H53 separates H44 family breadth from lexical breadth

- Preregistered concentration gates before any external H44 result, using
  inverse-Simpson effective counts and top-k row shares rather than treating
  611 repeated changes as independent trials.
- H44 spans 148 parent families; effective family count is 47.4782, top-one
  share 6.71%, and top-five share 24.71%. The family-breadth gate passes.
- H44 spans 286 NFKC/casefold/whitespace-normalized mention-specific units;
  effective lexical count is 89.7622 and misses the locked threshold of 100,
  although top-ten share is only 24.06%. The lexical-breadth gate fails.
- Reconciled the older 288 census: casefold-only reproduces 288, while strict
  normalization merges a canonically equivalent Unicode spelling and an
  embedded-newline variant. This is not a row-count discrepancy.
- Corrected the pre-result decision-tree semantics to “family-only breadth.”
  H44's ZIP, numerical gates and submission priority remain unchanged; no
  second artifact was created. Repeat reports are byte-identical at SHA-256
  `c633a4aee6956e03688b555b9a59de3d99bd42b098807902ff602129f2d17bc1`.

## 2026-08-03 — H54 shows H44 is mostly cross-family extrapolation

- Preregistered H23-seen versus H23-novel WHO-family strata before opening any
  external H44 metrics. The decomposition uses only frozen build reports.
- The H23-seen stratum contains 150 H44 rows (24.55%) across 28 families; the
  H23-novel stratum contains 461 rows (75.45%) across 120 families (81.08% of
  H44's family set). Both the novel-dominance and seen-subgroup materiality
  gates pass.
- Full H23-equivalent per-row scaling partitions the prior +1.4600 candidate
  forecast into +0.3584 for seen families and +1.1016 for novel families. This
  remains arithmetic exposure calibration, not hidden-gold prediction.
- Corrected the locked result semantics: negative H44 rejects indiscriminate
  cross-family expansion, not H23's observed CM-exclusive effect; strong
  positive specifically supports transfer into untouched families.
- Reports are byte-identical at SHA-256
  `78581a8156fc2816e14e7d5c8a2b67c7bcd86b6bfb4bbf3960b49e7b586d9592`;
  160 tests pass, H44 ZIP is unchanged and no subgroup artifact was created.

## 2026-08-03 — H55 closes H44 result-ingestion risk

- Explicitly stopped adding interpretive audits after H52-H54: exposure,
  breadth and interpolation-versus-extrapolation scope are now fully frozen.
- Built a recorder that loads the locked H44 YAML tree, verifies both submitted
  and local ZIP hashes, checks finite metrics, enforces WER/assertion
  invariance, reconciles `delta_score = 0.4 * delta_candidates`, and copies the
  first matching branch's interpretation and action.
- Wrong hash, WER movement, assertion movement and score-reconciliation failure
  all map to `STOP_ATTRIBUTION`; strong/small/null/negative fixtures map to
  `PROMOTE_H44`/`PROMOTE_H44_WEAK`/`RETAIN_H38`/`RETAIN_H38`.
- A fail-closed CLI check confirmed an invalid result creates no output file.
  Readiness reports are byte-identical at SHA-256
  `7293b2491f26727435879fa99e5b8ea4fb32fd828a439be071477d620d5f72ac`;
  164 tests pass and no external result or new submission artifact exists.
## 2026-08-03 — H44 external result rejects broad parent expansion

- Recorded the submitted SHA-256 through the fail-closed H55 recorder.
- H44 scored 35.4639 versus H38's 39.2813. WER and assertion Jaccard were
  invariant; candidate Jaccard fell by 9.5437, so the full loss is attributable
  to the 611 broad WHO-parent additions.
- The frozen decision tree selects `RETAIN_H38`. No further broad parent
  expansion is authorized.

## 2026-08-03 — H56 audits the reported file-size relationship

- Measured nine externally scored Turn-2 ZIPs using archive bytes, canonical
  JSON bytes and semantic counts.
- ZIP size correlates with score at 0.9817, but entity/assertion coverage has an
  equal or stronger association and the sequence is heavily confounded by
  architecture progress.
- V2 and H44 provide externally scored counterexamples to byte-size selection.
  Archive size is rejected as an objective; only independently supported
  semantic coverage may guide the next recall challenger.

## 2026-08-03 — H57 deterministic section-expert reconstruction

- A first full-document three-expert prompt was stopped fail-closed after the
  first record took about five minutes and two responses truncated. No quality
  result or ZIP existed when the protocol was amended.
- The deterministic chunked extractor completed 271/271 local Qwen3 calls and
  produced 2,738 proposals. Its conservative merger selected only 13 rows and
  failed the 150-row materiality gate; H57 closed without packaging.

## 2026-08-03 — H58 boundary-aware section-expert recall

- Preregistered only after H57 closed. H58 permits 55 shorter boundaries with
  Qwen-plus-encoder support and narrowly admits disjoint Qwen-only diagnoses,
  symptoms and numeric laboratory results.
- The first build failed its candidate-safety gate because two unsupported
  diagnoses inherited alias codes. Candidate assignment was fixed to require
  independent support, then the full build was rerun.
- Final census: 222 semantic changes, zero new nonempty candidate codes,
  100/100 valid records, exact ZIP member set, byte-identical repeat packaging
  and 170 passing tests. SHA-256 is
  `1789379ff5a091efe01477cd4c9b235c174624a2df8bedde752b420ac0e11b51`.
  No competition submission was performed.

## 2026-08-03 — H58 external rejection

- Recorded the submitted SHA-256 and organizer metrics from the user's result.
- H58 scored 37.7760, down 1.5053 from H38. All components regress: WER by
  +1.7125 unfavorable, assertion Jaccard by -2.3820 and candidate Jaccard by
  -0.6925.
- The score decomposition exactly reconciles to -1.50535 before display
  rounding. H58 is rejected and H38 remains the safe baseline.
- No follow-up ZIP was generated from this single aggregate result. In
  particular, supported-only or boundary-only variants would be unmeasured
  post-hoc micro-ablations rather than a demonstrated breakthrough.

## 2026-08-03 — H59 independent PhoNER boundary teacher

- Preregistered a new evidence source rather than another H58 threshold
  variant: the official, manually annotated PhoNER-COVID19 train/dev/test
  splits at revision `9af190aa76adcfad0a2d14fab9bcab2b252c9c2e`.
- The source `SYMPTOM_AND_DISEASE` label is converted to a combined clinical
  boundary target. It is never interpreted as the BTC diagnosis/symptom type.
- The source terms permit research/educational use and forbid redistribution;
  the dataset and trained checkpoint therefore remain local and untracked.
- The 17-page source guideline was reviewed in full. It favors complete spans
  with severity/stage modifiers but omits negated clinical mentions, so H59
  can provide positive exact-boundary support only and cannot justify deletion
  or assertion transfer.
- Frozen source gates require dev precision/F1 at least 0.90/0.65 and one-shot
  test precision/F1 at least 0.85/0.60. Target integration is H38 plus 20-100
  disjoint Qwen clinical rows with identical teacher offsets, with no baseline
  edits and no new nonempty candidate codes.
- Conversion produced 5,027 train sentences/1,439 mentions, 2,000 dev
  sentences/766 mentions and 3,000 test sentences/1,136 mentions. Five focused
  conversion, metric, threshold and exact-support tests pass. Training is in
  progress; no target ZIP exists at this checkpoint.

## 2026-08-03 — H59 outcome and H60 semantic rejection

- H59 selected epoch 2 and threshold 0.80. It passed source calibration with
  dev precision/F1 0.901084/0.884309 and test precision/F1
  0.921305/0.881543, but found zero exact supports among 131 H58 Qwen-only
  clinical proposals. The preregistered target gate failed; no H59 ZIP exists.
- H60 was registered from aggregate overlap counts before row-level text review.
  It produced 162 one-to-one containment replacements across 61 records and
  passed technical validation, but semantic audit found 45 single-token spans,
  33 spans at most three characters, and median new/old length ratio 0.466667.
  H60 is marked `DO_NOT_SUBMIT`; its local ZIP is retained only for audit.

## 2026-08-03 — H61 target-adaptive boundary model preregistration

- Registered task-adaptive masked-language pretraining on the unlabeled Turn2
  corpus before any H61 training. The encoder then receives the unchanged
  PhoNER source supervision and H59 source gates.
- Target gates were locked from the H60 failure signature: at least 600 exact
  H38 confirmations, 80-180 one-to-one nonexact clinical rows, <=10%
  single-token replacements, <=5 rows of at most three characters, and median
  new/old character ratio >=0.70.
- Added deterministic TAPT code and focused tests. No target output or H61
  checkpoint existed when the gates were locked.

## 2026-08-03 — H61 outcome

- TAPT completed three epochs with loss 8.180611→6.115009. PhoNER fine-tuning
  selected epoch 5 and passed all source gates at threshold 0.75.
- The Turn2 audit then failed every locked safety threshold: 539 exact H38
  confirmations, 184 replacements, 10.87% single-token rate, 17 very short
  rows and median length ratio 0.583333. No ZIP was created.

## 2026-08-03 — H62 assertion-only core registered

- Counted 553 historical, 181 negated and 61 family labels across H38 before
  model inference. Non-assertion entity fields and candidates are frozen.
- Registered a two-stage Qwen classifier/critic following the ConText concepts
  of trigger, scope, termination and pseudo-trigger. Only exact agreement with
  auditable evidence may alter a row; malformed/missing output retains H38.
- No H62 LLM label or output existed when the protocol was locked.

## 2026-08-03 — H62 direct pass and critic runtime amendment

- Direct pass completed 100/100 records and returned 2,445/2,448 eligible
  entities, with three missing rows and one malformed duplicate (0.123%
  missing). It disagrees with H38 on 813 rows across 95 records.
- The first critic calls returned all rows for records 1-3. Record 4's
  evidence-rich response truncated at about 9 KB and failed JSON parsing before
  any merged output or critic quality census existed.
- Amended only transport: critic batches contain at most ten disagreements.
  Prompt, model, temperature, labels, evidence contract and all gates remain
  frozen. Existing valid caches are preserved; invalid/missing rows retain H38.

## 2026-08-03 — H62 deadline checkpoint and rejection

- The critic reached 343/813 disagreements. Only 18 changes passed the frozen
  integration rule; 323 rows still disagreed between stages, one failed exact
  evidence, and one failed the removal-reason contract.
- A four-shard concurrency test completed only three additional records while
  contending for the same Ollama GPU, so it was stopped.
- The 18 accepted changes miss the locked 80-row minimum and the incomplete
  response census has 14.5354% missing/malformed items. H62 is rejected and no
  submission ZIP is generated. H38 remains the immediate safe artifact.

## 2026-08-03 — H41 independent reviewer agreement evaluation

- Double-annotations completed for Reviewer 1 (`6ec3707c343f...`) across 60 passages and Reviewer 2 (`e11d9f8cb207...`) across 15 holdout passages.
- Both checksums locked. Evaluated inter-reviewer agreement on the 15 holdout passages: strict span/type F1 = 0.4252 (gate >= 0.85, status: FALSE), assertion macro-Jaccard = 0.1317 (gate >= 0.80, status: FALSE).
- Because agreement gates failed, H63 supervised policy model training was canceled, gates were not modified, and no submission ZIP was generated.
- Baseline H38 (score 39.2813) remains the sole recommended submission artifact.

## 2026-08-04 — H63 provenance audit corrects H41 interpretation

- Inspected the committed reviewer builders and the untracked `scratch/`
  workflow. Reviewer 1 uses hard-coded passage cases, a generic keyword list
  and proximity assertion rules. Reviewer 2 used `detect_entities`,
  `CandidateResolver` and `infer_assertions` from the project pipeline.
- Both violate H41's frozen prohibition on rule/model prefill and reviewer
  exposure to pipeline outputs. The low agreement metrics cannot be treated as
  independent-reviewer evidence.
- The two files remain checksum-locked for audit but are quarantined from all
  training and submission decisions. The research direction pivots to an
  independent cross-lingual projection family.

## 2026-08-04 — H64 crosslingual clinical projection Stage 0 benchmark outcome

- Executed Stage 0 resource inventory and end-to-end benchmark on 50 public sentences using `Helsinki-NLP/opus-mt-vi-en`/`opus-mt-en-vi`, `d4data/biomedical-ner-all`, and `tner/xlm-roberta-base-bc5cdr`.
- Recorded resource manifest at `experiments/H64_crosslingual_clinical_projection/results/resource_manifest.json`.
- Benchmark result: **FAIL**
  - `projected_span_round_trip_rate`: **0.3758** (59/157 spans), failing the `>= 0.98` gate threshold (`false`). Translation/back-translation alignment distorts exact raw-text boundaries on 62.42% of projected mentions.
  - `estimated_full_turn2_wall_time_minutes`: **756.22 minutes** (~12.6 hours), failing the `<= 180.0` minutes gate ceiling (`false`).
- Under the frozen protocol rules, execution stopped immediately before Turn 2 inference.
- No challenger ZIP was created; baseline **H38 (39.2813)** is retained as the safe artifact.

## 2026-08-04 — H64 execution audit and H65 preregistration

- Static audit found the 50 benchmark lines came from Turn2 rather than public
  data. The script evaluates a raw union, counts any token overlap as success,
  and never implements two-model agreement, sentence alignment or exact
  accepted-span offset fidelity.
- The manifest's MPS claim is unsupported by code, and the ETA uses 2,500
  assumed lines versus 1,575 under its actual line rule. BC5CDR also limits
  consensus to two BTC types, making the three-type target gate unreachable.
- Reclassify H64 from a hypothesis rejection to invalid execution/inconclusive.
  The absence of a ZIP remains the correct safety outcome.
- H65 is committed before execution. It requires Colab CUDA, real device and
  revision evidence, a deterministic public sample, a broad-label
  DistilBERT/DeBERTa pair, separate alignment-yield and exact-offset metrics,
  public-gold calibration, and all inherited conservative fusion gates.
