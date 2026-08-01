# H19 — Reviewer-authoritative WHO ICD reconstruction

## Baseline

- Artifact: `turn2/output_v4_pair_qwen.zip`
- External score: 21.8139
- WER: 74.0072
- J_assertion: 30.7601
- J_candidates: 11.9700

## Failure found in H18

H18 preserved every old WHO-looking code even when the ontology reviewer
rejected it. Its alphabetical selector could also combine a category from one
disease family with a child from another. Several old values are semantically
impossible (`đại não` as brain cancer/trauma, `stent mạch vành` as a disease,
hospital-acquired pneumonia as J17).

## Intervention

Only diagnosis `candidates` may change. Text, type, positions, assertions and
all drug candidates are frozen byte-for-byte.

1. Use the frozen H18 proposer/reviewer evidence; make no new LLM call.
2. The reviewer is authoritative: a rejected old code is no longer preserved.
3. Keep only codes present in WHO ICD-10 2019.
4. Never combine parent and child codes from different three-character
   families. Multiple families are allowed only for explicitly compound text.
5. Apply a finite exact-surface correction table for high-certainty errors and
   missing codes. Every value must exist in the WHO catalogue.
6. Force anatomy, procedures and other non-diagnosis surfaces to an empty list.

## Acceptance criteria

- No cross-family parent/child pair.
- No non-WHO diagnosis code.
- All non-candidate fields are identical to V4.
- All 100 records validate and repeated builds are byte-identical.
- Manual audit of every exact override finds no clearly wrong family.

This is one candidate-policy experiment, not a blind micro-variant. Codex does
not submit it to the competition.
