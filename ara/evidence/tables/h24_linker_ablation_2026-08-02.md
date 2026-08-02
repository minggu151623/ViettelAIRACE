# H24 linker ablation — 2026-08-02

All values are Recall@k percentages on the frozen alias-group split derived
from 518 H23 weak links. They are not organizer ground truth.

| Method | Dev R@1 | Dev R@5 | Test R@1 | Test R@5 | Decision |
|---|---:|---:|---:|---:|---|
| Character TF-IDF | 11.11 | 11.11 | 10.71 | 17.86 | Frozen baseline |
| BamiBERT unadapted | 5.56 | 5.56 | 5.36 | 5.36 | Rejected |
| Alignment-only | 2.78 | 5.56 | 0.00 | 1.79 | Rejected; graph training canceled |
| Train-only prototypes | 2.78 | 2.78 | 5.36 | 8.93 | Rejected |
| Qwen3 Embedding | 8.33 | 22.22 | 14.29 | 26.79 | Pool generator |
| Type-specialist router | **16.67** | **25.00** | **17.86** | **30.36** | Promoted internally |
| Qwen reranker + graph | 5.56 | 27.78 | 17.86 | 30.36 | Rejected; no aggregate gain |
| Train-only feature classifier | 16.67 | 25.00 | 17.86 | 32.14 | Rejected; R@1 unchanged |

The union of Qwen and lexical top-10 candidates has an oracle Recall@1 of
30.56% on dev and 41.07% on test. This bounds the current reranking opportunity
but does not validate a leaderboard submission.

Evidence: `experiments/H24_ontology_graph_classifier/*/report.json`.
