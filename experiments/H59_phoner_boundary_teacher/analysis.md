# H59 result: source transfer passes, Qwen intersection fails

H59 trained for five epochs and selected epoch 2 by exact-span development F1.
The local checkpoint has model SHA-256
`a3d005f86d6ff4a377463b338cc49a79968dc183ccd639a4477ff901dd62b430`.

The frozen confidence selection chose threshold 0.80. It achieved 90.1084%
precision, 86.8146% recall and 88.4309% F1 on the official development split.
The one-shot official test result was 92.1305% precision, 84.5070% recall and
88.1543% F1. All source gates passed.

On Turn2 the teacher emitted 854 spans across 85 records. It exactly confirmed
653 H38 spans and overlapped 837 H38 spans, but exactly confirmed none of the
131 H58 Qwen-only clinical proposals. Consequently the preregistered 20-row
materiality gate failed and no H59 submission ZIP was created.

This refutes the specific Qwen-intersection mechanism, not the teacher. The
teacher's 653 exact confirmations show substantial target-domain alignment;
the 184 non-exact overlaps identify a separately testable resegmentation
hypothesis. H59 itself remains failed and may not be relaxed post hoc.
