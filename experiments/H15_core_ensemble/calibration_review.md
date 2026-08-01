# H15 blinded calibration review

This queue is intentionally independent of V6 and all proposal banks. Review
the raw text before opening any prediction output.

```bash
python -m airace annotate \
  --input input \
  --pred experiments/H15_core_ensemble/no_predictions \
  --out labels/h15_blind_calibration.jsonl \
  --records 19,21,25,31,34,38,60,69,72,76,85,95
```

Review priority:

1. exact `text`, `[start,end)`, and `type`;
2. repeated occurrences as separate rows;
3. assertions only where section/scope evidence is explicit;
4. candidates empty unless independently verified.

Do not copy V6 or model proposals into this file. It is a calibration set, not
a weak-label set. After all 12 records are reviewed, the merger may use a
train/calibration split, but the resulting score must still be described as a
small internal proxy rather than an estimate of leaderboard performance.
