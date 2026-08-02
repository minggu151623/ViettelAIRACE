# H39 dependency-aware label model analysis

## Outcome

H39 failed its second preregistered early gate and stopped before the contextual
stacker, assertion heads, ontology decoder, or artifact generation.

The synthetic correlated-noise benchmark passed decisively: unweighted
five-source majority reached 0.69350 positive-class F1, while the dependency-
aware label model reached 0.81017, a gain of 0.11667 against the required 0.05.
The run converged after 422 EM iterations and correctly reduced the two Bami
weights to approximately 0.185 each.

On the frozen real proposal universe, however, only 4 of 19 evaluable
type-by-held-out-family cells improved vote log-loss over majority. Failures
were broad rather than marginal. For example, held-out Bami symptom log-loss
worsened by 0.2693, held-out VietMed drug loss by 0.3972, and held-out H34 drug
loss by 1.3937. Test-result and patient-information cells were especially
poor because the remaining sources rarely express those policies.

## Interpretation

The real sources do not behave like noisy conditionally comparable annotators.
They implement different label inventories and boundary policies. A latent
confusion model can discount duplicated errors in a controlled simulation, but
cannot infer a common BTC policy from structurally non-isomorphic votes.

The failure policy therefore applies: no threshold relaxation, no stacker, and
no `output_v11` ZIP. The next direction must exploit independent corpus
structure or obtain prediction-blind annotation rather than estimate truth from
the same proposal banks.

## Reproducibility

- Frozen hashes matched.
- Candidate universe: 8,335 rows.
- Anchors: 48 positive controls, 21 registered hazards, 8 numeric measurements.
- Five focused tests and all 116 repository tests passed.
- Two early-gate runs produced byte-identical JSON with SHA-256
  `88340d4fb0013ae3752ac3df7a88c4fd6859db75b2d361d78853b0004e66e4a9`.
