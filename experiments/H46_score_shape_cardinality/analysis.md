# H46 analysis — score-shape cardinality

H46 exactly reproduced all 420 frozen H24 diagnosis rankings and trained only
on the 345 alias-group train rows. Ridge utility models over Qwen top-10 cosine
shape selected alpha 0.1 on the 28-row development fold.

The adaptive policy raised development diagnosis Jaccard from 0.071429 to
0.089286, an absolute gain of 0.017857. This is suggestive but fails every
registered reliability gate: the gain is below 0.02, the paired 10,000-sample
bootstrap interval is `[0.000000, 0.053571]`, and mean predicted cardinality is
3.107 rather than at most 3. The policy also emits very long prefixes for five
of 28 rows (`k=9` or `k=10`), exposing unstable extrapolation rather than
confident selective expansion.

The frozen test fold was therefore not evaluated. Two full audit reports are
byte-identical with SHA-256
`58573af96d2f6a3589ede0939be8bfd650335e2d6db7bdd9aaa8711c5745c8f5`.
All 137 repository tests pass. No ZIP was allowed or created.

Score shape contains weak cardinality information, but the current weak-link
development set is too small to establish a stable decision rule. Candidate
calibration now requires independent labels rather than another feature family.
