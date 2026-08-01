# Peer black-box evidence — candidate ablation

Source:
`https://competition.viettel.vn/api/forum/posts/019fa19e-1fdc-728e-a7c0-0b74469aa3b3`

Posted 2026-07-27 by a participant; there is no organizer reply at capture time.
This is independent leaderboard evidence, not official annotation policy.

## Reported controlled results

The participant reports:

| Submission | Reported final score | Reported `J_candidates` |
|---|---:|---:|
| 100 empty JSON arrays | 0.0773 | 0.1933 |
| 2,311 concepts with ICD/RxNorm candidates | not stated | 0 |
| Same 2,311 concepts with all candidates removed | 0.8938 | 0.8415 |

Because the entity set was reportedly identical between the last two runs, the candidate
field alone changed `J_candidates` by +0.8415 when removed.

## Interpretation

This independently reproduces the direction already observed in V5 -> V6:
unsupported codes are worse than empty candidates. It also suggests that a candidate
Jaccard of `0.1933` can arise from an entirely empty submission, so that value is an
empty/empty structural baseline rather than evidence of successful linking.

## Limits

- The organizer has not verified the report.
- The ZIPs and per-record outputs are unavailable, so entity identity cannot be audited.
- The display scale and full metric vector were not supplied.
- It does not establish which RxNorm/ICD convention is correct.

Use it to calibrate risk, not as ground truth.

## Independent corroboration

A separate participant post from 2026-07-26 reports `J_candidates` equal to exactly zero
despite emitting coded predictions and asks whether ICD formatting caused the failure:

`https://competition.viettel.vn/api/forum/posts/019f9c41-c14b-7332-a7b5-36a8de93ec46`

This second report has no paired no-candidate ablation, so it is weaker evidence, but it
shows that zero candidate credit with apparently populated codes is not unique to one team.
