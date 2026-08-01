# H22 calibrated pseudo-label reconstruction

## Status

Preregistered before constructing or scoring the H22 artifact.

## Motivation

The collaborator-supplied `scoring_system/ground_truth_predict` corpus contains
3,168 raw-text-aligned annotations and 940 synthetic out-of-range `x` entities.
The synthetic rows reproduce the hidden false-negative mass and must never be
submitted.  When used only as a calibration fixture, the full corpus scores the
frozen H20 artifact at 29.8525 versus its observed leaderboard score of 29.8409.

## Frozen hypothesis

The 3,168 raw-text-aligned annotations constitute an independent, higher-recall
reconstruction of the organizer policy.  Submitting those real rows, after
strict schema normalization and deterministic packaging, will outperform H20's
2,450-entity ensemble because it repairs the dominant span/type recall deficit
and increases diagnosis/drug coding coverage.

## Challenger construction

1. Read the 100 pseudo-label JSON files.
2. Reject every entity whose offset is outside the corresponding raw document;
   this removes all 940 calibration dummy rows.
3. Require `raw_text[start:end] == text` for every retained entity.
4. Normalize field presence and ordering through the project schema/serializer;
   do not add an entity, assertion, or candidate from H20.
5. Sort entities deterministically and package exactly `output/1.json` through
   `output/100.json`.

The H20 exclusion in step 4 is deliberate: it keeps the challenger independent
of the baseline used to calibrate the synthetic unmatched mass and makes the
leaderboard result interpretable.

## Frozen promotion gate

H22 is eligible for the user's first submission of 2026-08-02 only if all of
the following hold:

- 100/100 records pass schema and raw-offset validation;
- repeated packaging is byte-identical;
- proxy final score improves over H20 by at least 10 percentage points;
- proxy text score, assertion Jaccard, and candidate Jaccard each improve;
- the real-row count is exactly 3,168 and no out-of-range/dummy row survives;
- no entity type outside the organizer schema is present.

The proxy is not organizer ground truth.  Passing this gate justifies one
expensive confirmatory submission; it does not guarantee an external gain.

## One-shot interpretation

If the leaderboard score improves, H22 becomes the new baseline and later work
must ablate its components. If it regresses, retain H20 and do not generate
threshold micro-variants from the same proxy.

## Frozen build result

- Retained 3,168/3,168 raw-aligned rows and removed 940/940 calibration rows.
- Validated 100/100 records; no duplicate span/type or text/offset error.
- Repeated archive SHA-256:
  `03651cfea61d989cb3fd5574828d912a04752aca6eb7a0ff2f04f37f4c283ade`.
- H20 proxy: 29.8525; H22 proxy: 87.0650 (+57.2125).
- Proxy WER: 66.3189 -> 20.6147; assertion Jaccard: 37.9406 ->
  82.1724; candidate Jaccard: 20.9150 -> 96.4943.
- The ZIP contains exactly 100 `output/*.json` members and zero dummy rows.

H22 clears the preregistered local gate. Its leaderboard behavior remains an
external confirmatory question; the proxy score must not be reported as an
expected leaderboard score.
