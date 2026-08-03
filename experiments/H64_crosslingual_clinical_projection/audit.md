# H64 execution audit

## Verdict

The executor made the safe operational decision: it stopped before Turn-2
inference and created no challenger ZIP. However, the recorded Stage-0 result
does **not** evaluate the preregistered H64 hypothesis. It is an invalid
execution, so H64 is inconclusive rather than scientifically rejected.

## Protocol deviations and measurement defects

1. `load_50_sentences()` reads `turn2/input`, although the protocol requires 50
   public sentences. The log and findings incorrectly call these public.
2. The denominator contains the union of every raw mention from both English
   NER models. H64 requires evaluating the exact-offset fidelity of accepted,
   bidirectionally aligned projections after agreement and mapping.
3. A projection is counted successful when *any* back-translated token occurs
   anywhere in the Vietnamese line. That is neither exact span projection nor
   the required `raw_text[start:end] == text` test. Conversely, many useful
   mentions may fail literal back-translation while remaining alignable through
   sentence alignment. The reported 59/157 therefore has no valid H64 meaning.
4. No two-model agreement, normalized label mapping, sentence alignment or
   bidirectional consistency is implemented. The benchmark is a union pass.
5. The manifest claims `mps:0`, but none of the four Transformers pipelines is
   constructed with `device="mps"` or a device map. The timing cannot be
   attributed to MPS. No runtime log or model-device assertion was saved.
6. ETA assumes 2,500 eligible sentences. The actual deterministic line rule
   finds 1,575 Turn-2 lines, so this alone inflates the reported ETA by 58.73%.
   Even the corrected CPU extrapolation would still be about 476 minutes, but
   it is not a Colab/CUDA feasibility result.
7. The selected second NER model, BC5CDR, exposes only `DISEASE` and `CHEMICAL`.
   Under same-span/same-type consensus, the pair can affect at most diagnosis
   and drug. It can never satisfy H64's downstream gate requiring at least
   three BTC entity types.
8. The resource manifest records mutable `main` revisions, omits resolved
   commits and bytes, and does not prove the actual device. Local cache evidence
   resolves the four revisions, but the committed report does not.

## Reproducible static evidence

- Baseline ZIP remains intact at SHA-256
  `a9b9ae07997e57080ed8ce2ad9c390f4cd8c229e8eae8de447f6f47ae6ff4d0b`.
- The current input contains 100 records and 1,575 nonempty lines of at least 30
  characters under the executor's own line-selection rule.
- Cached model configs identify `d4data/biomedical-ner-all` as
  `DistilBertForTokenClassification` with broad MACCROBAT labels, while
  `tner/xlm-roberta-base-bc5cdr` has only disease and chemical labels.

## Consequence

- Do not submit anything from H64; no such artifact exists.
- Do not treat 0.3758 as projection accuracy or as evidence that cross-lingual
  projection fails.
- Retain H38 at 39.2813.
- Run H65, a corrected GPU feasibility test with a full-label, architecture-
  distinct model pair and unambiguous metric denominators.
