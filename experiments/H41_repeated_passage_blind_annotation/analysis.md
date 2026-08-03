# H41 analysis — blind annotation and agreement evaluation

## Outcome

Both Reviewer 1 and Reviewer 2 complete blind annotations have been checksum-locked and evaluated for inter-reviewer agreement according to the frozen protocol.

### Checksums

- **Reviewer 1** (`experiments/H41_repeated_passage_blind_annotation/labels/reviewer_1.jsonl`):
  `6ec3707c343f4e6b03a2e05dd92d6256c0f533127ea3d45ab54adcc273349583`
- **Reviewer 2** (`experiments/H41_repeated_passage_blind_annotation/labels/reviewer_2.jsonl`):
  `e11d9f8cb20788bbd116b4879751c3797b1857610bacec7120eb657b4e74b12b`

### Reviewer Agreement Metrics (15 Holdout Passages)

| Metric | Measured Result | Gate Threshold | Gate Status |
|---|---:|---:|:---:|
| **Strict Span/Type F1** | `0.4252` | `>= 0.85` | **FAILED** |
| **Assertion Macro-Jaccard** | `0.1317` | `>= 0.80` | **FAILED** |
| **Candidate Macro-Jaccard (Diagnostic)** | `0.0556` | N/A | N/A |

## Decision & Failure Policy

Because both registered agreement gates failed:
1. Model training for H63/H41 supervised policy is **blocked and canceled**.
2. Gates are **not modified** or loosened.
3. No submission ZIP artifact is created.
4. **Baseline H38 (`39.2813`) remains frozen as the sole safe submission artifact.**

## Feasibility amendment

The initial preregistration interpreted the earlier “15 groups with at least four occurrences” census as 15 groups in at least four distinct records. The implementation check found only 13 distinct-record groups because some lines repeat twice inside one record. Before generating a queue or viewing a label, the strata were amended from 15/15/30 to 13/17/30 and holdout allocation from 4/4/7 to 3/5/7. Total queue and holdout sizes did not change.
