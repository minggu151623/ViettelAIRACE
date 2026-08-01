# H20 external analysis

## External result

The user submitted `turn2/output_v6_expanded_pair.zip`. The leaderboard page
shows the registered hash prefix `ad5ac42a2fc3...`, confirming artifact identity.

| Metric | H17 baseline | H20 | Delta | Weighted delta |
|---|---:|---:|---:|---:|
| Score | 21.8139 | 29.8409 | +8.0270 | +8.02699 |
| WER | 74.0072 | 66.7969 | -7.2103 | +2.16309 |
| J_assertion | 30.7601 | 37.7055 | +6.9454 | +2.08362 |
| J_candidates | 11.9700 | 21.4207 | +9.4507 | +3.78028 |

The weighted decomposition uses the reconstructed organizer formula:
`0.3 * (100 - WER) + 0.3 * J_assertion + 0.4 * J_candidates`.

## Interpretation

All three components improve materially. This supports the combined H20
architecture: H19's reviewer-authoritative WHO candidate policy plus 500
disjoint exact learned-pair additions. Because both layers were submitted
together, the leaderboard result cannot isolate their individual effects.

The largest contribution is candidate normalization (47.1% of the gain), while
the WER reduction confirms that the expanded recall layer recovered genuine
gold mentions rather than only increasing false positives.

H20 is frozen as the new baseline. The next experiment should introduce a new
independent model/source or a principled overlap-replacement mechanism, not a
blind threshold variant.
