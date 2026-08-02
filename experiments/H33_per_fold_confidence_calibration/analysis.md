# H33 — Per-fold validation calibration

H33 failed. Per-fold thresholds raised aggregate precision/recall/F1 to
81.23/38.26/52.02%, but recall and F1 remained below 40/55% and fold 4 still
emitted zero predictions.

The failure is not explained by threshold portability alone. Fold 4's trainer
stopped after epoch three and retained its epoch-one checkpoint (validation F1
56.85%). H30 and the other four H32 folds trained through epoch eight; H30's
largest gains occurred after epoch four. The current early-stop rule can thus
terminate before a class-weighted encoder reaches its high-confidence regime.

A successor may add a preregistered minimum-epoch safeguard and rerun only the
failed fold as a falsification test. No agreement queue, ZIP or submission was
created.
