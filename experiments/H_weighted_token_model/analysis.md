# H6 result — Class-balanced clinical token model

## Result

The hypothesis passed the locked local decision rule. Weighted BamiBERT reached
strict span/type F1 `0.867470`, compared with `0.690476` for the previous
checkpoint:

- precision: `0.837209`;
- recall: `0.900000`;
- true positives: 36;
- false positives: 7;
- false negatives: 4;
- best epoch: 3.

The checkpoint is `models/bami-airace-v15-weighted`.

## Important implementation finding

Before this experiment, `airace/inference.py` required `heads.pt` and therefore
did not activate checkpoints saved as `model.safetensors`. Earlier token-model
output was actually the rule fallback. Checkpoint detection now recognizes
standard Hugging Face files, and the model/tokenizer are loaded once per run.

## Downstream decision

The raw model union was rejected because it added more than 600 spans. V16 uses
the weighted checkpoint only as the supervised student in a high-confidence
teacher–student agreement gate, while preserving V6 for assertions, drugs,
RxNorm, and all existing entities.

The 9-record holdout is V6-saturated and has influenced development, so its
score is not an unbiased leaderboard estimate. V16 remains an externally
untested candidate.
