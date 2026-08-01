# H14 — Test-name/result boundary audit

## Official policy evidence

The organizer confirms:

- test names and results are extracted independently;
- neither requires the other to exist;
- results may be numeric or textual;
- if a unit exists in the source, it belongs in the result span.

The older organizer overview also separates `WBC` from its numeric value rather than
putting the name and value into one `KẾT_QUẢ_XÉT_NGHIỆM`.

## V6 measurement

Across V6:

- 329 `TÊN_XÉT_NGHIỆM`;
- 235 `KẾT_QUẢ_XÉT_NGHIỆM`;
- 156 results contain a number;
- at least 52 numeric result spans also contain an obvious test-name token
  (`bạch cầu`, `ALT`, `AST`, `creatinine`, `kali`, `troponin`, etc.);
- 18 result spans geometrically overlap a separately emitted test-name span,
  including 16 cases where the result fully contains the name.

Examples:

- `bạch cầu 13.9` emitted only as result;
- `creatinine 5.7` emitted as result while `creatinine` is also emitted as a nested name;
- `troponin 0.01` emitted as result while `troponin` is also a nested name;
- `ast 421`, `alt 336`, `bilirubin toàn phần 0.9` emitted as result-only compounds.

## Interpretation

V6 often models a laboratory row as one compound result, while the BTC taxonomy asks
for independent name and result concepts. The minimum audited mismatch is 52 numeric
result spans containing a likely name; the true count may be higher for textual results.

This is a boundary/type-policy defect, not evidence that all long imaging findings should
be shortened. Official policy explicitly permits textual results, so imaging descriptions
need a separate analysis.

## Decision

Do not generate a broad test-result rewrite yet. First build a deterministic splitter
fixture for high-confidence numeric laboratory rows and evaluate it on an independently
annotated subset. Any future leaderboard experiment must change only this axis.

## Policy-derived fixture

`labels/policy_lab_numeric_fixture.jsonl` contains 15 high-confidence numeric laboratory
rows drawn from eight records. It covers name-before-value and value-before-name order,
parenthetical aliases, and a percent-valued measurement. Each name and result is stored
as an independent raw-text span.

These rows are policy-derived test fixtures, not organizer ground truth and not labels
inferred from leaderboard feedback. Their role is to test whether a deterministic
splitter implements the official independent-name/result policy consistently.

## Baseline detector probe

Running the current precision detector against this fixture recovers both exact spans
for only 4 of 15 rows (and at least one exact span for 5 of 15 rows). This is a
diagnostic of lexicon/row-pattern coverage, not a precision or recall estimate: the
fixture was constructed from policy evidence rather than exhaustive annotation.
The result supports keeping H14 focused on high-confidence numeric rows while
expanding the lab lexicon and handling both name-before-value and value-before-name
patterns in a separate, auditable implementation step.

## Experimental splitter

`airace/lab_splitter.py` now implements a conservative, opt-in numeric row splitter.
It handles name-before-value and value-before-name order, normalized Vietnamese `là`,
decimal/range values, and a fixed set of explicit units. Newline crossing is prohibited
so a value from one bullet cannot be attached to the test name on the next bullet.

The splitter passes all 15 policy-derived fixture rows plus explicit unit and textual-
finding rejection tests. The full project suite passes (35 tests). It is not connected
to inference or any submission artifact: this result demonstrates policy conformance
on the fixture, not hidden-set accuracy.

## Full-input risk audit

With the fixture names added to the bundled 23-name lexicon, the opt-in splitter
proposes 51 numeric pairs across 22 of the 100 inputs; 31 proposed pairs touch
an existing V6 span. Manual inspection found important risk classes that must be
gated before integration: `rr 14 spo2` can attach the preceding respiratory rate
to SpO2, `kali 80mEq` can be a supplementation instruction rather than a lab
result, and panels can contain multiple values on one line. These show why H14
must add section/action-context gates and must not be enabled globally yet.

Two conservative gates were then added: value-before-name rows must begin a
line/semicolon segment, and name-before-value rows are rejected when their local
prefix contains a treatment/action cue. The full-input proposal set fell from
51 pairs in 22 records to 48 pairs in 21 records; the known `spo2 <- 14` and
`kali <- 80` hazards are both absent. The complete suite now passes 36 tests.
Further manual review is still required before inference integration.

A second risk pass found two unsupported boundary classes: glued suffixes such as
`spo2 100ra`, and evolving values such as `creatinine 2.0 -> 3.2` or
`lactate 1.1-->0.8`. H14's first-stage protocol explicitly defers ambiguous
multi-value rows, so the splitter now rejects both classes instead of truncating
them. Proposals fell from 48 to 45 pairs across 19 records, and all 37 tests pass.

Against V6, 23 of the 45 proposed pairs are fully covered by an existing compound
`KẾT_QUẢ_XÉT_NGHIỆM` span; 14 pairs already have both exact independent spans.
This identifies the intended H14 edit surface without changing any output: at most
23 compound rows would be candidates for a name/result split, while the remaining
rows are additive or already partially represented.

The manual-review queue records the five highest-risk contexts (unusual panel
semantics, parenthetical vital-sign context, explanatory clauses, repeated
liver-panel occurrences, and overlapping calcium aliases). No row is promoted
to an external artifact until these invariants are checked independently.

Two consecutive full-input runs produced the same 45-row proposal serialization
(SHA-256 `585bde82ced0e1e4a05af90352315c51096d094242c5863ccf13c1b5ed033373`);
all emitted spans also passed raw-text offset checks. This establishes deterministic
reproducibility for the opt-in component.

A read-only dry-run applying splits only where a gated pair is fully covered by a V6
compound result would change 9 records (`5, 17, 37, 38, 39, 51, 56, 70, 84`).
Several rows contain existing nested/overlapping entities, so the dry-run flagged
7 overlap cases for review rather than silently rewriting them. No JSON or ZIP was
written.

Inspection of those seven warnings shows they are all existing exact or nested
`TÊN_XÉT_NGHIỆM` records inside the compound result (including the intentional
`cr`/`creatinine` aliases), not unrelated neighboring concepts. The future
transform therefore needs deterministic deduplication and longest-alias handling,
not a broad overlap deletion rule.

The alias rule is now covered by a regression test: for `canxi toàn phần` and
`canxi ion hóa`, the longest supported name is selected for each value and the
generic `canxi` subspan is not duplicated. The full project suite passes 38 tests.
