# Literature and method survey

This is a project-local method survey, not a claim that any cited method has
been validated on the hidden competition labels.

## Structured prediction and constrained generation

The project uses schema-constrained JSON parsing and structural validation. The
important practical lesson is that syntactic validity does not imply semantic
correctness: a valid list can still contain wrong spans, types, or candidates.
The rejected V7 structured-prompt experiment is the local evidence for this
distinction.

## Knowledge distillation and multi-teacher supervision

The installed knowledge-distillation skill recommends soft-target or
response-distillation approaches and explicitly supports multi-teacher
aggregation. For this task, the safe adaptation is proposal-level consensus:
use rule, VietMed-NER, and LLM outputs as competing hypotheses, then retain only
high-agreement or independently justified spans. Full logit distillation is
not currently feasible because the teachers do not share a compatible token
distribution and no gold labels are available.

## Evaluation methodology

The installed evaluation-harness skill emphasizes fixed task definitions,
reproducible configuration, checkpoint tracking, and saved per-example
predictions. We adapt those principles to a custom competition evaluator:
freeze metric definitions, save per-record diagnostics, and compare one
controlled change at a time. Standard MMLU/GSM8K-style tasks are irrelevant to
the clinical hidden-label score and will not be run as a proxy.

## Fine-tuning and tokenization

The installed tokenizer and PEFT skills are reserved for a later supervised
branch. They become appropriate only after creating a trustworthy annotation
set and a non-leaky validation split. Until then, they are documented as
future work rather than used to manufacture pseudo-ground truth.

## Public Vietnamese medical NER supervision

Four primary dataset sources were audited: ViMedNER, VietBioNER, ViMQ, and
VietMed-NER. ViMedNER has the closest taxonomy to BTC and is the preferred
technical candidate for encoder transfer; VietBioNER may help boundary
pretraining but merges disease and symptom; ViMQ and VietMed-NER have larger
domain mismatches. VietBioNER's README explicitly grants CC BY 4.0 and its
official repository is now pinned locally; ViMedNER, ViMQ, and VietMed-NER
remain license-blocked. See
`literature/vietnamese_medical_ner_dataset_audit.md`.
