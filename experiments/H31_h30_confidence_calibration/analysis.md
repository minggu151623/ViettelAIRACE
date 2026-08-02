# H31 — Frozen H30 confidence calibration

H31 passed every preregistered development and test gate.

The fixed grid selected confidence 0.90 on dev. Metrics were precision 81.60%,
recall 54.89% and exact span/type F1 65.63% (275 TP, 62 FP, 226 FN). The same
threshold was evaluated once on test and reached precision 84.53%, recall
49.12% and F1 62.14% (224 TP, 41 FP, 232 FN). Inference was deterministic and
all offsets were valid.

This does not authorize direct merging: H23 is still only a pseudo-target and
the single H30 model saw 70 records during training. H31 promotes confidence
0.90 only as an independent high-precision voter. The next experiment must
cross-fit predictions so every record is held out, then require exact agreement
with another independently constructed source before considering new spans.

No ZIP or competition submission was created.
