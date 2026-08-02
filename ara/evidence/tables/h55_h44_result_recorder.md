# H55 — H44 external-result recorder readiness

Protocol: `experiments/H55_h44_external_result_recorder/protocol.yaml`

| Synthetic case | Frozen branch | Decision |
|---|---|---|
| Wrong ZIP hash | validation_anomaly | STOP_ATTRIBUTION |
| WER movement | validation_anomaly | STOP_ATTRIBUTION |
| Assertion movement | validation_anomaly | STOP_ATTRIBUTION |
| Score reconciliation failure | validation_anomaly | STOP_ATTRIBUTION |
| Candidate Δ +0.50 | strong_positive | PROMOTE_H44 |
| Candidate Δ +0.10 | small_positive | PROMOTE_H44_WEAK |
| Candidate Δ +0.02 | practical_null | RETAIN_H38 |
| Candidate Δ -0.10 | negative | RETAIN_H38 |

An invalid CLI invocation was verified to exit without creating an output
file. The two readiness reports are byte-identical; all 164 repository tests
pass. These fixtures validate software behavior and are not external results.

Readiness SHA-256:
`7293b2491f26727435879fa99e5b8ea4fb32fd828a439be071477d620d5f72ac`.
Frozen decision-tree SHA-256:
`b5f6f63f9aea86e30742fff3db901f7fee1f492dc6cdfe17458ca7c2b1d8e9a8`.
