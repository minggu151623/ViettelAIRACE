# Organizer overview example recovered from a public snapshot

Source: [public snapshot of the original Track 2 overview](https://www.studocu.vn/vn/document/truong-dai-hoc-bach-khoa-dai-hoc-quoc-gia-thanh-pho-ho-chi-minh/mang-may-tinh/ai-race-2026-ontological-reasoning-in-medical-knowledge-retrieval/168063103), cross-checked against the public contest description at `https://competition.viettel.vn/contests/medical-2026`.

This overview predates the current round-specific PDF and contains a second
illustrative medical paragraph. It is useful for taxonomy, but not trustworthy
as character-exact gold because the snapshot contains OCR/formatting errors.

## Policy signals

- A reflux diagnosis is associated with more than one ICD candidate (a parent
  and a more-specific code). Therefore diagnosis `candidates` are not
  conceptually optional, even though V6 benefited from removing incorrect ICD
  guesses.
- Several symptoms are separate entities within one clause.
- Test names and result values are separate entities.
- Medication history receives `isHistorical`.
- The input mentions patient age and sex, but the summarized output does not
  list them. This weakens any assumption that every demographic phrase must be
  emitted as `THÔNG_TIN_BỆNH_NHÂN`.

## Reliability caveats

- The snapshot renders `WBC` in the input but `TWBC` in the output summary.
- Decimal drug strengths appear damaged by document extraction.
- The demonstrated RxCUIs were later challenged on the official forum as
  withdrawn or semantically inconsistent.
- No positions are supplied in this overview example.

Decision: use this source to constrain high-level policy only. Do not turn its
OCR strings into a golden span fixture.
