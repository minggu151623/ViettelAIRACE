# H14 manual review queue

This queue is for an eventual independent review before any external artifact. It is
not organizer gold and must not be used as hidden-label reconstruction.

## High-risk rows

- Record 39: `công thức máu là 32` — numeric adjacency is clear, but the
  measurement semantics are unusual and should be reviewed against the note context.
- Record 56: `SpO2 100% (không thở oxy)` — the numeric result is clear; decide
  whether the parenthetical belongs to the result or remains surrounding context.
- Record 37: `kali 6.3, mẫu không tan máu` — retain only the value in the first
  numeric intervention; do not absorb the explanatory clause.
- Record 70: repeated liver-panel occurrences — preserve each occurrence and
  avoid collapsing `alt`, `bilirubin toàn phần`, or their values.
- Record 100: overlapping aliases (`canxi`, `canxi toàn phần`, `canxi ion hóa`) —
  select the longest supported name at each value without deleting distinct
  occurrences.

## Review invariants

1. Every emitted span must satisfy `raw_text[start:end] == text`.
2. A split changes only the targeted compound result and its independent test name.
3. Assertions/candidates outside the targeted rows remain byte-identical.
4. Ambiguous trends, glued suffixes, treatment doses, and unsupported textual
   results remain deferred.
