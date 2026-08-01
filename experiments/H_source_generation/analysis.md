# H12 — Source-generation audit

## Question

Are the 100 public records raw Vietnamese clinical notes, or translated/restructured
derivatives of another clinical corpus?

## Direct observations

A deterministic scan of all 100 inputs found highly repeated template headings:

| Normalized line | Files |
|---|---:|
| `đánh giá tại bệnh viện` | 74 |
| `tiền sử bệnh hiện tại` | 52 |
| `tiền sử bệnh` | 48 |
| `tiền sử bệnh nội khoa` | 39 |
| `triệu chứng hiện tại` | 33 |
| `bệnh sử hiện tại` | 32 |
| `các sự kiện trước khi nhập viện` | 31 |
| `đặc điểm triệu chứng` | 27 |
| `diễn biến bệnh` | 23 |
| `các bệnh lý mãn tính` | 18 |

The ZIP metadata is also batch-like: all 100 text members have the identical DOS
timestamp `2026-06-20 22:03:36`, identical create-system/version fields, and the
archive reports MS-DOS/NT FAT provenance. This supports common export/packaging,
though it cannot reveal the annotation process.

Twenty-six files retain mixed English clinical strings such as `nausea`, `diarrhea`,
`abdominal pain`, `daily`, `bid`, `prn`, `dced`, `sp CABG`, `CT`, and `MRI`. There are
also translation/restructuring artifacts such as `Nhập viện gần đây vì Đã tử vong
(dced)`, duplicated phrases, and partly translated medication instructions.

## Interpretation

The public set is strongly consistent with a common translation/restructuring pipeline,
not 100 independently authored Vietnamese notes. Combined with the previously documented
i2b2-like problem/test/treatment schema, this raises a testable source hypothesis:
organizer labels may have been transferred or adapted from structured concepts in an
English clinical corpus before/while generating the Vietnamese text.

This does **not** establish that the source is i2b2, MIMIC, or any other named corpus.
Web searches of several distinctive English back-translations did not recover an indexed
source note. The named-source claim remains unproven.

Primary i2b2 sources confirm that its task used semi-structured discharge summaries and
progress notes from three hospital sources, including MIMIC II, and that access is now
through the n2c2 portal under a Data Use Agreement. This strengthens task-family
resemblance but does not provide record-level alignment. See
`literature/source_corpus_provenance_assessment.md`.

## Consequences

1. Section/template position is likely a high-value feature for annotation and assertion
   policy.
2. English abbreviations and residual English symptoms must remain first-class lexicon
   entries; a Vietnamese-only detector is structurally incomplete.
3. Repeated narrative content may be a generation artifact but, by official forum policy,
   each textual occurrence still needs its own entity.
4. Do not train directly on i2b2 labels until an actual source alignment is recovered.

No output artifact was generated from this audit.
