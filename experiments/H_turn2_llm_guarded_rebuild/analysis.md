# H-T2 analysis — guarded LLM rebuild

## Outcome

The intervention satisfies all locked structural criteria and externally
improves the score from `16.6673` to `19.0709`.

| Measure | Turn 2 baseline | Guarded LLM |
|---|---:|---:|
| Entities | 1,486 | 1,540 |
| Empty records | 6 | 0 |
| Diagnosis | 414 | 435 |
| Symptom | 596 | 617 |
| Test name | 193 | 204 |
| Test result | 111 | 111 |
| Drug | 172 | 173 |
| Candidate IDs removed | 0 | 104 |
| Exact safe candidate additions/replacements | 0 | 44 |

## Interpretation

The broad prompt is refuted as a direct output generator because it frequently
labels recommendations and lifestyle actions as symptoms. It remains useful
as a second teacher. The structured prompt is supported for clinical prefixes,
but still requires deterministic type repair. Candidate review is useful only
with ontology safeguards: the LLM incorrectly rejected some valid parent codes
despite the prompt explicitly allowing them.

External evaluation improved every component: text credit by `1.9259`,
J_assertion by `2.1250`, and J_candidates by `2.9707`. Candidate changes
contributed `1.1883` of the total `2.4036` gain after metric weighting.

## Reproducibility

- Raw-LF validation: 100/100.
- Test suite: 49/49.
- Two independent JSON builds: byte-identical.
- Two independent ZIP builds: identical SHA-256
  `6fd8212e1d1c77e83dbdfd0de973b197c147ada6eb059c28abe8e0daba2e8dcb`.
- No competition submission was made.
