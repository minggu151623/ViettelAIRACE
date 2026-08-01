# Leaderboard-scale metric reconstruction

The public page labels WER as a percentage error, while its contribution to
the final score is the complementary text score. Three independent scored
submissions reproduce the displayed total (to the four shown decimals) with:

```text
final = 0.3 * (100 - WER) + 0.3 * J_assertion + 0.4 * J_candidates
```

All four displayed quantities are on the 0–100 page scale. This is equivalent
to the internal evaluator's `0.3*(1-WER_fraction) + ...` after multiplying by
100.

Consequences for research prioritization:

- At V6's WER of 99.9602, the **current** text contribution is only `0.01194`
  points. Reducing WER to zero would add `29.98806` points.
- One full displayed point of candidate Jaccard is worth `0.4` final-score
  points; one assertion point is worth `0.3`.
- Text/entity matching is therefore the largest immediate failure, not a
  saturated component. Candidate and assertion policy remain high-leverage,
  but small candidate-only repairs cannot compensate for WER near 100%.

This is a reconstruction from published scoreboard values, not a claim about
the undisclosed matcher.
