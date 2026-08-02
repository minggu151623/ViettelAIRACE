# H36 controlled novel verifier — result

Status: **passed**.

The frozen dual-prompt verifier reviewed the 51 H35 novel agreements together
with 30 deterministic positive controls. It retained 27/30 controls (90%),
rejected both registered fused-token hazards, produced complete responses, and
reached 92.59% action agreement between the semantic and boundary prompts. All
offsets remain exact.

It accepted 42 novel spans: 29 `TRIỆU_CHỨNG`, eight `CHẨN_ĐOÁN`, and five
`THUỐC`. The nine rejected rows include both registered hazards and multiple
incomplete, generic, or unsupported boundaries. This is evidence that the
controlled verifier adds useful precision after independent source agreement.

Per the preregistration, these rows are a verified queue only. They are not
merged directly and no submission ZIP is created by H36. The next experiment
must freeze this queue and test assertion/candidate enrichment. The first
integration should isolate symptoms because they do not require ICD/RxNorm
candidates.
