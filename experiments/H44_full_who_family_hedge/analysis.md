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
