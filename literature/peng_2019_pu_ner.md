# Distantly Supervised Named Entity Recognition using Positive-Unlabeled Learning

- Authors: Minlong Peng, Xiaoyu Xing, Qi Zhang, Jinlan Fu, Xuanjing Huang
- Venue/year: ACL 2019
- DOI: 10.18653/v1/P19-1231
- Primary source: https://aclanthology.org/P19-1231/

The paper formulates incomplete dictionary supervision for NER as
positive-unlabeled learning. Its relevant principle is that tokens or mentions
not found by a weak annotator must not automatically become negative examples.
The competition adaptation is proposal-level rather than token-level: H23 exact
matches are positives, while proposal-bank spans absent from H23 remain
unlabeled. This paper does not validate the BTC taxonomy or our pseudo labels.
