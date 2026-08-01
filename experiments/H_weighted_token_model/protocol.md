# H6 — Class-balanced clinical token model

## Status

Protocol locked before execution.

## Observation

The previously trained BamiBERT checkpoint was silently disabled during
inference because the pipeline required a legacy `heads.pt` file instead of the
Hugging Face `model.safetensors` checkpoint. After fixing this, the real model
achieved strict F1 0.690476 on the reviewed holdout, including symptom recall
1.0, but predicted almost no drugs or lab results.

## Hypothesis

The unweighted BIO cross-entropy is dominated by `O`, symptom, and diagnosis
tokens. Inverse-frequency class weighting should improve rare `THUỐC`,
`TÊN_XÉT_NGHIỆM`, and `KẾT_QUẢ_XÉT_NGHIỆM` recall without reducing overall
strict F1 below the 0.690476 checkpoint baseline.

## Controlled variables

- Same 91 silver training records.
- Same 9 reviewed validation records.
- Same BamiBERT base checkpoint.
- Same tokenizer, max length 256, stride 64, seed 42.
- Same optimizer, learning-rate schedule, and early stopping.
- Only the token-class loss weighting changes.

## Prediction and decision rule

Keep the weighted checkpoint only if:

1. overall strict validation F1 exceeds 0.690476; and
2. at least one rare class gains a true positive; and
3. symptom recall remains at least 0.90.

Otherwise reject weighted training and retain the existing checkpoint.

## Submission rule

No leaderboard ZIP will be produced directly from this experiment. A model
must first pass the validation rule and a separate hybrid ablation that keeps
the V6 RxNorm candidate policy.
