# Frozen Turn 2 baseline — 29.8409

This document is the handoff anchor for the best externally scored artifact as
of 2026-08-01. Do not overwrite the files named below. New work belongs in a
new experiment directory and must treat this baseline as the fallback.

## Artifact identity

- Submission: `turn2/output_v6_expanded_pair.zip`
- Extracted JSON: `turn2/output_v6_expanded_pair/`
- Input: `turn2/input/`
- Input archive: `turn2/input_turn2_vong1.zip`
- Submission SHA-256:
  `ad5ac42a2fc3d0105537c42873d4aaeba1e24aef57ec9510216cf32f43d25691`
- Registered leaderboard hash prefix: `ad5ac42a2fc3...`

The submitted file was recovered locally with a `.txt` suffix but verified as
a valid ZIP archive. It has been renamed to `.zip` without changing its bytes.

## External metrics

| Metric | Value |
|---|---:|
| Overall score | 29.8409 |
| WER | 66.7969 |
| J_assertion | 37.7055 |
| J_candidates | 21.4207 |
| num_scored | 100 |
| num_records | 100 |

The reconstructed organizer formula is:

```text
0.3 * (100 - WER) + 0.3 * J_assertion + 0.4 * J_candidates
```

## Architecture

H20 starts from H19's reviewer-authoritative WHO candidate policy and adds 500
disjoint exact learned-pair spans. The proposal sources are VietMed-NER,
Bami-v15, Bami-v3 and bounded Qwen adjudication. Qwen may accept or reject a
fixed proposal but does not invent offsets. Diagnosis candidates use the exact
WHO table; medication candidates use the local RxNorm CPC resolver with strict
strength matching. Assertions are recomputed by the deterministic local scope
engine.

The two major changes were submitted together, so the leaderboard result does
not isolate their individual effects. Read the complete protocol and evidence
under `experiments/H19_turn2_who_precision/` and
`experiments/H20_turn2_expanded_pair/`.

## Verification

```bash
shasum -a 256 turn2/output_v6_expanded_pair.zip
python -m airace validate \
  --input turn2/input \
  --output turn2/output_v6_expanded_pair
python -m pytest -q
```

Expected validator summary:

```text
records: 100
CHẨN_ĐOÁN: 632
TRIỆU_CHỨNG: 1190
TÊN_XÉT_NGHIỆM: 262
THUỐC: 255
KẾT_QUẢ_XÉT_NGHIỆM: 111
```

At freeze time all 57 tests pass.

## Collaboration rule

Do not tune directly against the public leaderboard and do not replace this
artifact with an unscored variant. Each challenger should record its hypothesis,
changed files, local evaluation, output checksum and external result in its own
`experiments/<id>/` directory. Promote a challenger only after it passes the
blind-validation gate and the user confirms its leaderboard score.

