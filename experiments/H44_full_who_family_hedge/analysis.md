# H44 analysis — full WHO family hedge

H44 scales the externally positive H23 mechanism from 144 CM-exclusive rows to
all 611 eligible singleton diagnosis-specific rows in H38. The transform spans
97 records and changes only `candidates`, from `[specific]` to
`[WHO three-character parent, specific]`.

All registered structural gates pass: 3,226 entities and every text, type,
position, assertion, drug candidate and noneligible diagnosis candidate are
frozen; all 100 files validate. Two full output builds and deterministic ZIP
packages are byte-identical. The submission archive SHA-256 is
`5e451dd4f728ee2acecad80e364b5f750f11064941d1055031e7653aed3c83ba`.

This is a deliberately high-upside hierarchy-policy test. H23 established the
direction externally, but H44 tests whether it generalizes beyond ontology-
exclusive rows. WER and assertion Jaccard should remain invariant; leaderboard
movement should be candidate-derived.

H53 audits the intervention distribution before the score is revealed. The
611 rows cover 148 parent families, with an inverse-Simpson effective count of
47.48 and only 24.71% of rows in the top five families, so the registered
family-breadth gate passes. They cover 286 NFKC/casefold/whitespace-normalized
mention-specific pairs, but the inverse-Simpson effective count is 89.76,
below the registered lexical-breadth threshold of 100; the lexical gate fails.
The old census of 288 used casefold only, while the stricter normalization
merges one canonically equivalent Unicode pair and one embedded-newline pair.

Accordingly, a positive external H44 result can establish broad WHO-family
transfer but not broad surface-form transfer. This semantic correction leaves
the artifact, submission priority and numerical decision gates unchanged.

H54 further separates interpolation from extrapolation. Only 150 H44 rows
(24.55%) across 28 parent families occur in families previously touched by
H23. The other 461 rows (75.45%) span 120 previously untouched families, or
81.08% of H44's family set. Both frozen dominance thresholds pass. H44 is thus
primarily a cross-family extrapolation test, while its 150-row seen-family
stratum is independently large enough for a separately preregistered
post-result ablation if aggregate evidence warrants one. A negative H44 result
would reject indiscriminate expansion into new families, not erase H23's
observed CM-exclusive gain. No subgroup artifact has been built.
