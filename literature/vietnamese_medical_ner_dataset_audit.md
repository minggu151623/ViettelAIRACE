# Vietnamese medical NER dataset audit

Captured 2026-07-28 from primary paper/repository sources. This audit distinguishes
technical relevance from permission to use; a public repository without an explicit
dataset license is not treated as licensed training data.

## ViMedNER

- Paper: https://doi.org/10.4108/eetinis.v11i3.5221
- Repository: https://github.com/tdtrinh11/ViMedNer
- Data present: `train.txt` (~1.83 MB), `dev.txt` (~0.61 MB), `test.txt`
  (~0.61 MB).
- Taxonomy: disease, symptom, cause, diagnostic, treatment.
- Relevance: closest public Vietnamese taxonomy to BTC; disease/symptom/diagnostic/
  treatment can provide representation transfer, although BTC separates test name,
  result, drug, and patient information.
- Evidence: expert annotation with reported high agreement; the paper reports XLM-R
  as the strongest evaluated baseline.
- License risk: the repository declares no SPDX license. The article is
  CC BY-NC-SA 4.0, but that does not automatically establish permission for the
  repository dataset. Do not train until dataset licensing is clarified.

## VietBioNER

- Paper: https://aclanthology.org/2022.lrec-1.385/
- Repository: https://github.com/ptpuyen1511/VietBioNER
- Data present: BRAT annotations from two annotators plus supervised/few-shot splits.
- Taxonomy: Organisation, Location, Date/Time, combined Symptom-and-Disease, and
  Diagnostic Procedure.
- Relevance: useful for Vietnamese biomedical boundary pretraining, but narrower
  tuberculosis/scientific-document domain and a combined disease/symptom class limit
  direct BTC label transfer.
- Evidence: the paper reports per-category inter-annotator F-score from 70.59% to
  95.89% and supervised models outperforming dictionary/few-shot baselines.
- License: the repository README explicitly declares CC BY 4.0. GitHub's SPDX
  metadata is empty because there is no standalone recognized license file, but
  the upstream license statement is clear enough for attributed research use.
- Local provenance: official repository commit
  `19ba70a5947d1be72906d407c860b1666b9337e9` is vendored read-only under
  `external/VietBioNER`; split checksums are recorded separately.

## ViMQ

- Repository: https://github.com/tadeephuy/ViMQ
- Data present: train/dev/test JSON for medical question intent classification and NER.
- Relevance: Vietnamese healthcare vocabulary, but dialogue questions differ strongly
  from hospital-note structure.
- License risk: no SPDX license declared.

## VietMed-NER

- Paper/model card: https://arxiv.org/abs/2406.13337 and
  https://huggingface.co/leduckhai/VietMed-NER
- Data/model: public spoken medical NER with 18 entity types and text/ASR variants.
- Relevance: useful domain encoder/teacher prior; the current project already uses its
  model only within a consensus path.
- License risk: neither the GitHub repository nor Hugging Face dataset card declares
  an explicit license.

## Decision

ViMedNER is the most promising supervised-transfer source because its taxonomy is
closest to BTC and its data are large enough for encoder fine-tuning, but it remains
license-blocked. VietBioNER is cleared under CC BY 4.0 and can be used for attributed
boundary/diagnostic-procedure pretraining. Its combined disease/symptom class must
never be mapped directly to both BTC types.
