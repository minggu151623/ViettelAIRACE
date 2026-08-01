# H13 — V6 assertion-policy audit

## Scope

Read-only audit of all 2,254 V6 entities against:

- the organizer's metric wording (assertions are compared for disease, drug, symptom);
- official forum confirmation that assertions are multilabel;
- the i2b2 experiencer definition used only as an external policy prior.

No output was changed.

## Distribution

V6 emits:

| Type / assertion | Count |
|---|---:|
| `CHẨN_ĐOÁN` / `isHistorical` | 155 |
| `TRIỆU_CHỨNG` / `isNegated` | 60 |
| `THUỐC` / `isHistorical` | 53 |
| `TRIỆU_CHỨNG` / `isHistorical` | 44 |
| `TRIỆU_CHỨNG` / `isFamily` | 15 |
| test/result assertions of any kind | 15 |
| `CHẨN_ĐOÁN` / `isFamily` | 2 |
| `THUỐC` / `isFamily` | 1 |
| `TÊN_XÉT_NGHIỆM` / `isFamily` | 1 |

## High-confidence failure: reporter is not experiencer

There are 19 total `isFamily` labels. Manual context review finds only one plausible
non-patient experiencer:

- file 77: `Mẹ Đã tử vong...` -> `tử vong`.

The other 18 describe the patient, even when a relative is the reporter:

- `Người nhà nhận thấy bệnh nhân ... mất định hướng`;
- `Gia đình nhận thấy ... khó khăn khi cài cúc áo`;
- `Theo lời người nhà kể lại bệnh nhân ... buồn chán`;
- patient medication `gleevec`;
- diagnoses/results with no family experiencer at all.

Under the experiencer definition, “reported by family” must not imply `isFamily`;
the condition must belong to the relative. Thus 18/19 V6 family labels are semantically
contradictory under the independent prior.

## Test/result assertion mismatch

V6 attaches 15 assertions to `TÊN_XÉT_NGHIỆM` or `KẾT_QUẢ_XÉT_NGHIỆM`. The organizer's
metric description names disease, drug, and symptom as assertion-bearing concepts. This
is evidence of policy risk, though the organizer has not explicitly said test assertions
are forbidden in the JSON schema.

## Black-box caution

V10 included family/test assertion cleanup together with other changes and externally
regressed. Therefore that run cannot refute this audit; it is confounded.

## V11 scope correction (2026-07-28)

V11 is schema-isolated—its text, type, position, and candidate fields are
byte-equivalent to V6—but it is **not** an isolated experiencer test. A
read-only comparison finds 176 changed assertion rows: 144 add
`isHistorical`, 16 remove `isFamily`, 10 remove `isNegated`, and six make other
mixed changes. The existing artifact can measure a broad assertion-policy
recalculation only; it cannot by itself confirm or refute the family-reporter
hypothesis. The reproducible audit is in `code/audit_assertion_delta.py` and
`results/v11_delta_audit.json`. No new artifact was generated.

The broad historical change is nevertheless structured rather than arbitrary:
all 147 V11 additions of `isHistorical` (including three rows that also had a
family transition) are in the explicit numbered history section detected from
the raw note. None relies on a loose nearby-word cue. This strengthens the
semantic rationale for V11 as a broad assertion-policy artifact, while leaving
its family-specific causal interpretation unresolved. The independent section
audit is stored in `results/historical_addition_audit.json`.

## Decision

Treat experiencer detection as a semantic-role rule:

`relative is experiencer` != `relative is reporter of patient's condition`.

Do not generate another micro-variant. Preserve this finding for a future
preregistered assertion evaluation with a clearly named scope.
