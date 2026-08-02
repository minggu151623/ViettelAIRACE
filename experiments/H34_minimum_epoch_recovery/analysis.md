# H34 — Minimum-epoch recovery

The trainer fix worked, but H34 narrowly failed one preregistered fold gate.

Preventing early stopping before epoch five caused the failed fold to train all
eight epochs. Its inference precision/recall/F1 changed from 100/0/0% (empty)
to 87.41/39.43/54.35%. The fold recall gate required 40%, so the experiment is
formally failed by 0.57 percentage points.

After substitution, aggregate out-of-fold precision/recall/F1 is
82.23/46.15/59.12%, passing all aggregate gates with 1,462 TP, 316 FP and 1,706
FN. This validates the minimum-epoch safeguard as a trainer correction, but the
agreement queue remained closed under the protocol.

A successor may audit the already frozen combined OOF predictions to measure
independent agreement. It may not relax H34 retroactively or merge spans. No ZIP
or competition submission was created.
