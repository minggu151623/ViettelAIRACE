# H30 — Weak-label Bami adaptation

H30 failed its development gate and test was canceled.

The best checkpoint after eight epochs reached strict exact span/type precision
57.44%, recall 72.46% and F1 64.08% against the 501 H23 dev entities. Offsets
were valid. Diagnosis F1 was 70.47%; test result was weakest at 46.30%.

Class weighting produced the intended recall but too many positives: 363 true
positives, 269 false positives and 138 false negatives. The learning curve was
still improving through epoch eight, but the registered training budget ended
and neither the 82% precision nor F1 gate was close.

The checkpoint is rejected as a direct proposal model. A separately registered
confidence calibration may test whether its high-recall predictions contain a
useful precision subset; test remains closed until that dev gate passes. No ZIP
or competition submission was created.
