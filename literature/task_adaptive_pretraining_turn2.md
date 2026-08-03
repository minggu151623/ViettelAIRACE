# Task-adaptive pretraining for Turn2 domain shift

Gururangan et al., [Don't Stop Pretraining: Adapt Language Models to Domains
and Tasks](https://aclanthology.org/2020.acl-main.740/), report that continued
masked-language pretraining on unlabelled task data can improve downstream
transfer, including after broader domain pretraining.

H61 adapts only this mechanism. It uses the 100 public Turn2 inputs without
labels for masked-language modelling, then repeats H59's frozen human-labelled
PhoNER fine-tuning and source calibration. No H38, Qwen, hidden metric or
leaderboard result enters either training objective.

This addresses the observed failure directly: H59 performs well on PhoNER but
fragments many Turn2 multiword clinical mentions. The paper supports trying a
target-domain language-model phase; it does not imply that source annotation
policy, BTC type policy or exact boundaries become correct. H61 therefore has
separate source and target integrity gates and fails closed.
