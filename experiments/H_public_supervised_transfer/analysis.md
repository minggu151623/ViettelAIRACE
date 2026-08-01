# H6 — VietBioNER diagnostic-procedure transfer result

## Setup

- Base: `cbc-528a/BamiBERT-ViMedNER` cached snapshot
  `e508eedd34d124e05cf139cc565806c6d4fc5aad`.
- Training: 706 source sentences / 191 retained `TÊN_XÉT_NGHIỆM` entities.
- Validation: separate 300 sentences / 89 entities.
- Device: MPS; maximum 12 epochs, early stopping after 4.

## Result

Best strict source span/type F1 was **0.462745** at epoch 2:

| Precision | Recall | TP | FP | FN |
|---:|---:|---:|---:|---:|
| 0.355422 | 0.662921 | 59 | 107 | 30 |

The model over-predicts diagnostic-procedure spans. This does not meet the
precision required for a proposal source in a competition where excessive entities
are heavily penalized. It is therefore rejected for inference integration and no BTC
artifact is generated.

## Confidence calibration

Threshold calibration on the same held-out source validation set cannot rescue the
checkpoint. The best F1 is 0.525822 at threshold 0.70 (precision 0.451613, recall
0.629213); the highest nontrivial precision is only 0.5, at thresholds 0.85 and 0.90,
where recall falls to 0.415730 and 0.044944 respectively. The full curve is saved in
`results/threshold_calibration.json`.

## Interpretation

The cleared dataset was valuable for a legal, reproducible test: its biomedical
literature domain and narrow 191-entity training signal do not transfer cleanly to
the templated hospital-note test-name policy. Future supervised work needs more
aligned licensed labels; this model cannot be made precision-safe merely through a
threshold and must not be tuned on the 100 inputs.
