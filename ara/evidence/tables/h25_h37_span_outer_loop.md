# H25–H37 span outer-loop evidence

| Experiment | Frozen evaluation | Result | Decision |
|---|---:|---:|---|
| H25 PU proposal classifier | record-held-out dev/test | F1 gain +0.39/+0.40 pp; addition precision 41.67/36.84% | reject |
| H26 phrase policy | train-only lexicon to dev/test | F1 gain +4.08/+1.32 pp; addition precision 50.59/36.11% | proposal source only |
| H27 dual verifier | dev | control retention 81.40%; pseudo-precision gain +10.82 pp | reject |
| H29 boundary prompt | dev corruption/control | recovery 37.07%; control retention 70.13% | reject |
| H30 token adaptation | record-held-out dev | P/R/F1 57.44/72.46/64.08% | reject direct use |
| H31 confidence calibration | dev/test | P 81.60/84.53%; F1 65.63/62.14% | voter only |
| H32/H33 crossfit calibration | 100 OOF records | F1 50.89/52.02%; one empty fold | reject |
| H34 minimum-epoch recovery | failed fold + aggregate | fold F1 54.35%; aggregate P/R/F1 82.23/46.15/59.12% | repair retained |
| H35 independent audit | frozen OOF | 51 novel exact agreements; two known hazards | queue only |
| H36 controlled verifier | 30 controls + 51 novel | 90% controls; 100% hazards dropped; 42 accepted | pass queue |
| H37 symptom integration | 100 records | 22 boundary rows + 4 additions; 108 tests; deterministic | candidate artifact |

Leaderboard evaluation remains pending for H37. No organizer submission was
performed by the AI.
