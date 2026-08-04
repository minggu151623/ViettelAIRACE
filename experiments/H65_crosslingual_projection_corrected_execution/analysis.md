# H65 Stage 0 analysis

Status: **FAIL — stop before Stage 1, Turn2 inference and ZIP creation.**

The protocol-faithful CUDA run completed on 50 deterministic PhoNER dev
sentences. It produced seven exact same-normalized-mention/same-type English
NER agreements across three mapped BTC types, but no agreed mention
back-translated to a literal raw Vietnamese substring. Consequently alignment
yield, exact-offset fidelity and public precision/recall/F1 are all zero.

Three gates fail:

- exact offset fidelity `0.00 < 0.98`;
- alignment yield `0.00 < 0.15`;
- accepted materiality `0 < 20`.

CUDA, structural three-type coverage and runtime pass. Runtime is not the
bottleneck: 7.44 seconds for the 50-sentence benchmark and 3.91 estimated
minutes for 1,575 target lines.

The materiality failure is decisive independently of literal back-translation:
even a perfect aligner could accept at most the seven existing exact English
consensus mentions, below the frozen minimum of 20. H65 therefore rejects the
combination of exact English mention consensus plus literal mention
back-translation. It does not reject cross-lingual transfer generally.

No threshold is changed after observing the report. H38 remains the safe
externally verified artifact at 39.2813.
