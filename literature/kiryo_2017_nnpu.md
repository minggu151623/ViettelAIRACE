# Positive-Unlabeled Learning with Non-Negative Risk Estimator

- Authors: Ryuichi Kiryo, Gang Niu, Marthinus C. du Plessis, Masashi Sugiyama
- Venue/year: NeurIPS 2017
- Primary source: https://proceedings.neurips.cc/paper/2017/hash/7cce53cf90577442771720a370c3c723-Abstract.html

The paper shows that an unbiased PU risk estimator can become negative and
overfit when a flexible model is trained from limited positives. It proposes a
non-negative correction. H25 adopts the conservative implication rather than
copying the neural estimator: use regularized bagged linear classifiers,
record-held-out evaluation, and stability constraints before accepting any
unlabeled proposal.
