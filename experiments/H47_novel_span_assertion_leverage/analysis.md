# H47 analysis — novel-span assertion leverage

The repeated sign is real but the observed leverage is too small for a reset
slot. H37 adds 26 exact novel entity keys, of which seven carry assertions over
six records; H38 adds 183, of which 29 carry assertions over 18 records. Every
asserted novel entity has exactly one assertion. `isHistorical` dominates
(27/36 labels), followed by `isNegated` (7/36) and `isFamily` (2/36).

The externally observed assertion losses contribute only 0.03903 weighted
score points for H37 and 0.00702 for H38, or 0.04605 combined. This is an
evidence-leverage diagnostic, not a mathematical upper bound on a hypothetical
counterfactual. It nevertheless fails the preregistered 0.10 threshold despite
passing the recurrence, cohort-size and record-coverage gates.

Proposal-derived assertion abstention is closed as a reset-slot mechanism. No
altered output directory or ZIP was written. Two reports are byte-identical at
SHA-256 `e1d511bf507170e4cc698a8dfbe7e8ee7b1a64b96d882cca061aedf746e7c349`;
all 139 repository tests pass.
