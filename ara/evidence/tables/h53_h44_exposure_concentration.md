# H53 — H44 exposure concentration

Protocol: `experiments/H53_h44_exposure_concentration/protocol.yaml`

| Metric | H23 | H44 |
|---|---:|---:|
| Changed rows | 144 | 611 |
| Affected records | 46 | 97 |
| Unique parent families | 57 | 148 |
| Effective parent families | 36.251748 | 47.478189 |
| Top-five parent row share | 0.243056 | 0.247136 |
| Strict normalized lexical units | 89 | 286 |
| Effective lexical units | 64.800000 | 89.762202 |
| Top-ten lexical row share | 0.270833 | 0.240589 |

Registered H44 family breadth passes. Registered lexical breadth fails because
the effective lexical count is below 100. Casefold-only normalization
reproduces the earlier H44 census of 288; NFKC plus whitespace collapse merges
one Unicode-equivalent spelling pair and one embedded-newline pair. Input row
count remains 611.

The repeat result is byte-identical. Result SHA-256:
`c633a4aee6956e03688b555b9a59de3d99bd42b098807902ff602129f2d17bc1`.
The H44 artifact remains
`5e451dd4f728ee2acecad80e364b5f750f11064941d1055031e7653aed3c83ba`.
