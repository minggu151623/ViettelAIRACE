# H28 — Constrained boundary selector

H28 stopped before model inference. The preregistered ±4-token enumerator
contained the H23 target span for only 325/392 eligible development entities
(82.91%), below the 95% gate.

The dominant failure is mechanical: a first/last-token seed from a six-to-eight
token mention needs up to seven tokens of expansion. A smaller set of failures
comes from pseudo-target spans whose endpoints are inside a whitespace token or
include outer punctuation. Those rows are not valid evidence for a token-boundary
selector.

No LLM decisions were requested, the test split was not inspected, and no ZIP
was created. A successor must define eligibility as token-boundary-aligned and
use a window capable of reconstructing every eligible span before inference.
