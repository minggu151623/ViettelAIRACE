# Official round-1 sample — boundary policy audit

Source: `AI Race 2026 - Cuộc đua AI cho kỹ sư Việt Nam.pdf`, pages 2-6.

This audit uses only the sample printed by the organizer. It does not infer hidden labels.

## Directly observed rules

1. **Medication spans retain administration detail.** The sample keeps strength, route,
   dose form, frequency, and PRN text inside `THUỐC`, for example:
   `nystatin oral suspension 5 ml po qid:prn`.
2. **Medication spans stop before indication language.** The cue `điều trị` and the
   following condition are not part of the drug span.
3. **Indications are separate symptoms.** `ho`, `đau nhức`, `sốt đau`, `táo bón`,
   `lo âu`, and `mất ngủ` are emitted as `TRIỆU_CHỨNG`.
4. **Every repeated occurrence is separate.** `táo bón` and `lo âu` each appear twice
   and receive two records with distinct positions.
5. **The section controls history.** Every medication under “Danh sách thuốc trước nhập
   viện” receives `isHistorical`; the indication symptoms receive an empty assertion
   list.
6. **Symptom segmentation is lexical/contextual, not a universal whitespace rule.**
   The organizer keeps `sốt đau` as one span but splits `lo âu mất ngủ` into `lo âu`
   and `mất ngủ`. Therefore an automatic “always split adjacent known symptoms” or
   “always keep the full tail after điều trị” rule is contradicted by the same sample.

## Comparison with the i2b2 policy prior

| Rule | Official BTC sample | i2b2 prior | Assessment |
|---|---|---|---|
| Keep drug modifiers | full dosing detail kept | keep non-assertion modifiers | agrees |
| Exclude assertion/section cues from span | `điều trị` excluded | assertion modifiers excluded | agrees |
| Repeated occurrence | separate records | separate annotations | agrees |
| Independent symptom list | mixed (`sốt đau` kept; `lo âu mất ngủ` split) | split independent items | partial/ambiguous |
| Historical medication | yes | original assertion task applies to problems and is time-independent | BTC-specific divergence |

## Consequence for experiments

Do not perform a global compound-symptom split/merge ablation. Any boundary change for
adjacent symptoms needs phrase-level evidence or independent annotation. The stable rule
that can be tested safely is the medication/indication boundary, but V6 already reproduces
the official fixture and must not be changed without a separate audit.
