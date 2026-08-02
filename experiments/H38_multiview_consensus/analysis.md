# H38 multi-view consensus analysis

## Outcome

H38 passed its preregistered local gates and produced a candidate artifact. It
is not an external result and has not been submitted.

- 301 exact rows absent from H37 had support from at least three of five frozen
  proposal views.
- 209 were structurally eligible (`disjoint` or contained within an H37 entity
  of the same type).
- The frozen dual verifier accepted 189 rows before candidate filtering. Five
  unsupported disjoint diagnosis/drug rows were removed and deterministic
  new-to-new overlap resolution left 183 rows.
- The accepted rows comprise 132 symptoms, 25 diagnoses, 16 test names and 10
  drugs across 68 records.
- Integration replaces 130 H37 rows and adds 183 rows, for a net increase of
  53 entities. Unaffected entities are dictionary-identical to H37.

## Controls and reproducibility

- Frozen-source checksums: all match the preregistration.
- Positive-control retention: 44/48 = 91.67% (gate: at least 85%).
- Registered-hazard rejection: 21/21 = 100%.
- Semantic/boundary prompt agreement: 90.29% (gate: at least 80%).
- Schema and offsets: 100/100 records valid.
- Project tests: 110 passed.
- Two complete reruns produced identical output trees and ZIP bytes. ZIP
  SHA-256: `a9b9ae07997e57080ed8ce2ad9c390f4cd8c229e8eae8de447f6f47ae6ff4d0b`.

## Residual risk

Exact multi-model agreement is not ground truth because the proposal models
share weak-label ancestry. A manual anomaly audit found one clear correlated
error: `38.3°C` is accepted as `TRIỆU_CHỨNG`, although it is a measurement.
Short context-dependent spans such as `đau`, `sốt`, and `mụn` also remain.
Candidate-bearing contained replacements inherit the candidate tuple from the
larger H37 span; this is defensible for most drug cores but can over-specify a
shortened diagnosis such as `Bệnh tim mạch` with `I25.1`.

These observations do not authorize post-hoc deletion from H38. They define a
future preregistered semantic-compatibility safeguard. H38 remains a materially
larger, controlled black-box candidate, not a claimed guaranteed improvement.
