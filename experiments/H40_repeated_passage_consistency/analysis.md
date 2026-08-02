# H40 repeated-passage consistency analysis

## Outcome

H40 failed two preregistered early gates and stopped before integration or ZIP
creation.

- Exact repeated-line census reproduced: 271 groups, 610 occurrences, 83
  records.
- The selector proposed 346 canonical entities over 122 affected groups and
  would make 551 row additions/removals, above the registered 400-row ceiling.
- Leave-one-occurrence-out canonical stability was 152/172 = 88.37%, below the
  required 95%.
- Positive-control retention passed at 47/48 = 97.92%; hazards and cross-type
  ties were excluded as registered.

The failure is not a formatting issue. Most repeated groups have only two
occurrences, and even groups with three or more often rely on an entity supported
by exactly two occurrences. Removing either supporting occurrence changes the
canonical policy. Exact repetition exposes annotation inconsistency but cannot
resolve it automatically without an independent label.

## Decision

Do not tune support thresholds or integrate a smaller post-hoc subset. Reuse
the repeated passage library as an annotation multiplier: a prediction-blind
human label on one unique passage can be projected to every exact occurrence.

## Reproducibility

All 119 repository tests pass. Two early-gate runs produced byte-identical JSON
with SHA-256 `d83069fd0cb67944849735e508a2080a84d9f8d4eea26f1f02b2d845227e4db0`.
