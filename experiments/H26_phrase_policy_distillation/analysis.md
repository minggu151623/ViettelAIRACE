# H26 analysis — train-only phrase policy distillation

## Decision

The mechanism is promising but fails the submission gate. Retain it as a new
proposal source and require contextual verification before any merge.

## Result

Dev selected a case-insensitive, boundary-aware lexicon with minimum support in
two distinct train records. It contains 235 phrases across five entity types.

| Split | H20 strict F1 | With phrase additions | Gain | True additions | Addition precision |
|---|---:|---:|---:|---:|---:|
| dev | 52.14% | 56.22% | +4.08 pp | 43 | 50.59% |
| test | 55.95% | 57.27% | +1.32 pp | 26 | 36.11% |

The experiment passes the dev gain and minimum true-addition gates but fails
test gain and both precision gates. It creates no ZIP.

## Interpretation

Repeated annotation phrases transfer across held-out records, confirming that
the templated corpus carries learnable boundary/type policy. Exact phrase
matching alone is context-blind: `mạch` in anatomy is not a test name, `phù`
inside `phù hợp` is not edema, and `bình thường` is a result only when attached
to an actual test. Conversely, many H23-absent matches such as clinical `ngã`
are semantically plausible hidden positives, so absence from H23 cannot be
treated as proof of error.

The next component should review phrase proposals in their local section and
sentence. It must preserve high-recall H23 matches while rejecting known
homonyms, substring boundaries and generic educational prose.
