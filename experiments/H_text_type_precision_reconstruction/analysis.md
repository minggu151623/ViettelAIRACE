# H1 analysis — boundary, assertion-domain, and drug-span repair

## Classification

The original H1 confirmatory criterion cannot distinguish this run because the
9-record reviewed holdout was already saturated at 40/40 by V6 and had been
used during rule development. The boundary repair is therefore recorded as an
**exploratory, high-confidence correctness fix**, not as a confirmed
leaderboard improvement.

## Changes

- Removed 39 short symptom fragments embedded inside larger words:
  - 33 instances of `ho` inside words such as `thoáng`, `khoa`, `khoảng`,
    `hoặc`, and `cho`;
  - 6 truncated fragments such as `ngà`, `ngấ`, `nga`, and `nồn`.
- Repaired four drug spans while preserving their existing RxCUI:
  - `Tăng liều bactrim` → `bactrim` (two occurrences);
  - `propofol để an thần` → `propofol`;
  - `lasixđã dừng cách vài tuần` → `lasix`.
- Restricted assertions to `CHẨN_ĐOÁN`, `THUỐC`, and `TRIỆU_CHỨNG`, following
  the official PDF.
- Replaced substring-based family detection. The old rule matched `bố` inside
  `bối cảnh` and treated phrases reported by `người nhà`/`gia đình` as diseases
  of the family member.
- Added numbered-section inheritance so relevant entities in section
  `1. Tiền sử ...` receive `isHistorical`.

## Measured outcome

- Entities: 2,254 → 2,215.
- Records changed: 56/100.
- Removed span keys: 43; added corrected span keys: 4.
- Assertion changes on retained spans: 173.
- Reviewed holdout: still 40/40 strict span/type.
- Official example fixture: 19/19 with reconstructed final score 1.0.
- Validator: 0 errors across 100 records.
- Tests: 28 passed.
- Repeated directory generation: byte-identical.

## Interpretation

The removed spans are mechanically impossible concept boundaries, so this
change has a stronger justification than earlier heuristic pruning. The
assertion changes correct two concrete implementation bugs and add
section-level history propagation. However, no hidden-label gain can be claimed
until the organizer scores the ZIP.

## Artifact

- Directory: `output_v10_research_precision_btc/`
- ZIP: `output_v10_research_precision_btc.zip`
- SHA256:
  `45912c7cf9b56410f06d97c2895115f51db198932efc2e9127fbe2a3d435af1e`

## External result

The organizer scored the ZIP at **1.6368**, below the V6 baseline of 1.7280:

- WER: `99.9602 → 99.9597`
- J_assertion: `2.9216 → 2.7942`
- J_candidates: `2.0991 → 1.9663`

The combined intervention is therefore rejected. The local holdout and
official fixture were insufficient to predict the hidden-label behavior.
