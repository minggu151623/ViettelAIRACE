# H21 initial analysis

## Implemented evidence

- The selector reads only raw UTF-8 text. It computes character length, line,
  section, bullet and colon-row counts; no prediction path is accepted by the
  API.
- Eighteen records were selected across six length strata with seed `298409`.
  Each stratum contributes two development records and one holdout record.
- The full corpus and each selected raw record are protected by SHA-256 in the
  manifest. Editing or replacing the Turn 2 input invalidates evaluation.
- Repeating manifest generation produced a byte-identical file.
- The annotation UI can open a manifest split while using an intentionally
  empty prediction directory.
- The paired evaluator validates raw annotation text, entity offsets, baseline
  predictions and challenger predictions before scoring.
- A missing-label smoke run returned `INCOMPLETE_ANNOTATIONS`, demonstrating
  that the gate fails closed.
- Synthetic fixtures confirm that a uniformly better challenger can promote,
  bootstrap output is deterministic and modified input is rejected.
- The project suite increased from 57 to 61 passing tests.

## Current conclusion

The evaluation machinery is ready, but no empirical claim about a new model is
made before independent annotation. H20 remains the champion. The next valid
inner-loop measurement requires completing the 12-record development queue;
the six-record holdout must remain untouched until a challenger is frozen.

