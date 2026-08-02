# H45 analysis — Jaccard-aware candidate cardinality

H45 is a negative but decisive internal result. On the frozen H24 alias-group
split, dev macro-Jaccard selected `k=1` globally and separately for diagnosis
and drug. The one-shot test result therefore exactly matched the singleton
baseline at 0.178571; the paired 10,000-resample delta and both confidence
bounds were 0. Fixed expansion was actively harmful: test Jaccard fell to
0.107143 at `k=2`, 0.060119 at `k=5`, and 0.039123 at `k=10`.

The per-row prefix oracle reaches 0.233099, leaving 0.054528 absolute headroom.
That gap is not evidence that a broader list should be emitted: it shows that
the ranking lacks a calibrated row-level signal for choosing when additional
candidates are worth their Jaccard denominator penalty. The weak labels are not
organizer gold, so this result cannot select a competition artifact.

The registered promotion gate fails and no ZIP is permitted or created. H24
remains a proposal retriever. H44 remains scientifically distinct because it
tests an externally supported same-family parent/specific policy, not an
arbitrary top-k recall expansion.
