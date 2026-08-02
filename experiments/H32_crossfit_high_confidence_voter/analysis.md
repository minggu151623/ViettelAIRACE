# H32 — Five-fold high-confidence cross-fit

H32 failed its aggregate recall/F1 gates. Across 100 out-of-fold records,
confidence 0.90 produced precision 83.06%, recall 36.68% and exact F1 50.89%
(1,162 TP, 237 FP, 2,006 FN). Offsets were valid.

Four folds retained useful precision (79.34–86.27%), but fold 4's early-stopped
checkpoint emitted no entity above 0.90. Its F1 was zero. Therefore a confidence
threshold calibrated on one checkpoint is not portable across independently
fine-tuned folds, even when architecture and training settings match.

The agreement queue was not generated because the aggregate gate failed. The
five frozen checkpoints may be reused only by a separately preregistered
per-fold calibration using each fold's disjoint validation records. No ZIP or
competition submission was created.
