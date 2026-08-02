# H52 — H44 exposure and transfer calibration

An exploratory audit found that H44's external decision tree incorrectly
described 467 rows as being beyond H23. Stable identity matching by record,
exact position and preserved specific code confirms that H23's 144 changes and
H44's 611 changes have zero overlap. H44 therefore adds 611 new interventions,
and the two stages cover 755 distinct occurrence-level parent hedges.

## Pre-result arithmetic

H23 improved external candidate Jaccard by 0.3441 across 144 changed rows, or
0.00238958 candidate points per changed row. Linear exposure scaling gives:

- 100% H23-equivalent per-row yield across H44: `+1.460035` candidate Jaccard;
- corresponding total-score delta: `+0.584014`;
- forecast from H38: `39.865314`.

The locked H44 gates therefore correspond to:

| Gate | Candidate delta | Equivalent H23 per-row yield retained |
|---|---:|---:|
| Practical | +0.02 | 1.3698% |
| Strong | +0.50 | 34.2457% |
| Full linear transfer | +1.4600 | 100% |

These ratios normalize exposure only. Candidate evaluation weights depend on
unknown gold sets and may differ systematically between CM-exclusive H23 rows
and broader H44 rows. The forecast is not a prevalence estimate or score
guarantee.

## Decision-tree correction

The numerical gates and branch order remain unchanged. The tree now states 611
additional disjoint rows and interprets strong positive as material transfer
of at least 34.25% H23-equivalent yield—not proof that mixed hierarchy is a
universal corpus policy. The correction was committed before any H44 external
result. H44's ZIP and SHA-256 are unchanged, and no second artifact exists.

Repeat reports are byte-identical at SHA-256
`a635b2e992898177daa8603e8bbefb0200c8eac3ba6c39745c06626bb12287c0`.
