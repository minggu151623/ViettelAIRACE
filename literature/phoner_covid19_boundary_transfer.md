# PhoNER-COVID19 as an independent boundary teacher

## Decision

Use the official PhoNER-COVID19 corpus only to train and calibrate an exact
clinical-mention boundary verifier. Do not use it to choose the Viettel labels
`CHẨN_ĐOÁN` and `TRIỆU_CHỨNG`, because PhoNER deliberately combines both into
`SYMPTOM_AND_DISEASE`.

## Evidence

- Truong, Dao and Nguyen introduce a manually annotated Vietnamese dataset of
  10 entity types and report sequence-labelling baselines. The work directly
  supports Vietnamese boundary supervision, but the COVID-news domain differs
  from the competition's clinical records:
  <https://aclanthology.org/2021.naacl-main.173/>.
- The official repository defines the dataset terms as research/educational
  use only and prohibits redistribution of the original or modified data:
  <https://github.com/VinAIResearch/PhoNER_COVID19>.
- Biomedical linking work commonly separates mention representation/retrieval
  from concept ranking. This supports the narrower use of a boundary model as
  one independent signal rather than as an end-to-end BTC annotator:
  <https://aclanthology.org/2021.louhi-1.4/>.
- Aggregate weak supervision cannot generally guarantee recovery of latent
  labels without assumptions. Therefore this experiment must be calibrated on
  the official human-labelled development split and may still fail closed:
  <https://arxiv.org/abs/2411.06200>.

## Frozen transfer rule

The verifier may approve a Qwen proposal only when the start and end offsets
match exactly above a development-calibrated threshold. Qwen retains its BTC
type. The verifier cannot add an entity by itself, repair a boundary, change a
baseline entity, or introduce a candidate code.

This is intentionally more conservative than H58: the new evidence is an
independent human-labelled corpus, while the target intervention remains an
intersection rather than a union.
