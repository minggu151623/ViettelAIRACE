# H17 analysis — independent pair plus Qwen adjudication

## Result

The frozen confidence and source policy produced 72 eligible rows from the
pair-only proposal mass. Qwen retained 66 rows under both temperature-zero
seed runs:

- 46 symptoms
- 16 diagnoses
- 4 test names

The six rejected rows remain quarantined. No drug, test-result, or
Bami-v15+Bami-v3-only proposal was admitted. The merge grows H16 from 1,884 to
1,950 entities.

## Audit

Context review found the accepted rows dominated by explicit mentions such as
`rung nhĩ`, `thuyên tắc phổi`, `chụp CT`, `đau đầu`, and `khó thở`. Ambiguous
rows such as `thiếu máu` are retained only with the fixed type agreed by the two
learned models and Qwen. The obvious-error rate in the reviewed list remains
below the preregistered 10% ceiling.

The two Qwen runs produced identical decisions. Because decoding used
temperature zero, this demonstrates deterministic stability rather than two
statistically independent LLM votes; the evidence should be interpreted as one
Qwen adjudicator layered on two learned sources.

An exploratory assertion audit exposed that `phủ nhận` was missing from the
negation grammar. The cue was added and unit-tested, correctly assigning
`isNegated` to the newly accepted `Phủ nhận buồn nôn` row. Existing H16 fields
remain frozen.

## Verification

- 54/54 tests pass.
- 100/100 output files validate against raw LF input.
- Two builds and ZIPs are byte-identical.
- SHA-256: `f217efeb117611338dc5dd810058f8cd45fb2e5c60fe9622d370ce09aabf9ce1`.

## Artifact

`turn2/output_v4_pair_qwen.zip`

No competition submission was performed.
