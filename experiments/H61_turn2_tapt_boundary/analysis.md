# H61 — Turn2 task-adaptive boundary model

## Result

Task-adaptive masked-language pretraining reduced mean loss from 8.180611 to
6.115009 over three epochs. Subsequent PhoNER fine-tuning selected epoch 5.
The locked source calibration passes at threshold 0.75: dev precision/F1 are
0.900671/0.888154 and one-shot test precision/F1 are 0.895327/0.868540.

## Target gate

The blind Turn2 audit fails every boundary-safety gate that distinguishes H61
from H60: 539 exact H38 confirmations, 184 one-to-one nonexact rows, 10.87%
single-token replacements, 17 replacements of at most three characters, and
median new/old character ratio 0.583333.

## Decision

No submission ZIP is created. TAPT improves the source development optimum but
does not remove target-domain fragmentation. H38 remains the safe baseline.
