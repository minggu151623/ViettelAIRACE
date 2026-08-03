# H44 external result and H56 archive-size audit

| Comparison | ZIP bytes | Entities | Candidates | Assertions | Score |
|---|---:|---:|---:|---:|---:|
| Turn-2 baseline | 69,802 | 1,486 | 515 | 283 | 16.6673 |
| V2 guarded | 64,975 | 1,540 | 455 | 285 | 19.0709 |
| H38 | 97,509 | 3,226 | 1,219 | 795 | 39.2813 |
| H44 | 95,869 | 3,226 | 1,830 | 795 | 35.4639 |

H44 has identical WER (`56.1576`) and assertion Jaccard (`47.3920`) to H38;
candidate Jaccard alone falls from `29.7776` to `20.2339`. This binds the
negative movement to broad candidate expansion and rejects archive size as a
causal objective.
