# H67 literature synthesis — exact ontology linking under no organizer gold

## Kết luận nghiên cứu

Các paper không ủng hộ việc ghép nhiều checkpoint nguyên bản rồi vote. Cơ chế
lặp lại nhất quán là:

1. học code identity từ synonym thật;
2. retrieve bằng sparse+dense;
3. mine các mã gần nhưng sai làm hard negatives;
4. dùng graph để biểu diễn neighborhood, không đánh đồng node gần nhau;
5. rerank bằng mention context;
6. hiệu chỉnh để abstain khi chưa chắc.

Đây cũng là phần H24 chưa thực hiện thành công: H24 fit trên 518 weak links của
pipeline, không ontology-only family-held-out supervision; generic reranker và
linear classifier không cải thiện R@1.

## Nguồn chính và phần được áp dụng

### BioSyn

[Biomedical Entity Representations with Synonym Marginalization](https://aclanthology.org/2020.acl-main.335/)
trộn sparse character representation và dense representation, đồng thời cập
nhật model-based candidates để các negative ngày càng khó. H67 giữ character
2–5-gram trong retrieval pool và mine negative từ top predictions, thay vì coi
lexical retrieval là baseline phải bỏ.

### SapBERT

[Self-Alignment Pretraining for Biomedical Entity Representations](https://aclanthology.org/2021.naacl-main.334/)
cho thấy same-concept synonyms là supervision có thể mở rộng mà không cần task
labels. H67 dùng official RxNorm synonyms và validated ICD multilingual aliases
làm positives. H38/H24 predictions không được biến thành same-code gold.

### KRISSBERT

[Knowledge-Rich Self-Supervision for Biomedical Entity Linking](https://aclanthology.org/2022.findings-emnlp.61/)
tạo self-supervised mention examples từ ontology và unlabeled text, sau đó dùng
contextual prototypes. H67 chỉ tạo public Vietnamese context anchor khi một
exact alias maps duy nhất tới một code; Turn2 bị khóa đến sau calibration.

### BERGAMOT

[Biomedical Entity Representation with Graph-Augmented Multi-Objective Transformer](https://aclanthology.org/2024.findings-naacl.288/)
kết hợp term-term, term-node, node-node contrastive objectives với Deep Graph
Infomax trên multilingual graph. Paper báo zero-shot state-of-the-art trên phần
lớn các ngôn ngữ của Mantra và XL-BEL. H67 dùng relation-aware adapter, DGI và
intermodal term-node alignment, nhưng thay đổi một chi tiết quan trọng theo
bằng chứng cuộc thi: parent/child/sibling là exact-code hard negatives. Chúng
không được kéo lại gần như interchangeable positives.

### Cross-lingual BEL

[Learning Domain-Specialised Representations for Cross-Lingual Biomedical Entity Linking](https://aclanthology.org/2021.acl-short.72/)
chỉ ra knowledge-enhanced English models còn khoảng cách lớn khi chuyển ngôn
ngữ. Vì vậy H67 không dùng checkpoint English-only nguyên bản; Qwen3/BGE chỉ là
multilingual proposal views và mọi gain phải xuất hiện trên family-held-out
multilingual supervision.

### Con2GEN

[Controllable Contrastive Generation for Multilingual Biomedical Entity Linking](https://aclanthology.org/2023.emnlp-main.350/)
biểu diễn concept bằng một câu template chứa nhiều chiều ontology. H67 áp dụng
ý này ở input reranker: canonical name, hierarchy/path và structured RxNorm
ingredient/strength/form/route được đưa vào cùng mention context. H67 không cho
decoder sinh code tự do; code luôn bị giới hạn trong ontology pool.

### RxNorm official model

[RxNorm Current Prescribable Content](https://www.nlm.nih.gov/research/umls/rxnorm/docs/prescribe.html)
là subset public-domain/no-license, gồm active normalized names, RxCUIs,
attributes và relations trong RXNCONSO/RXNSAT/RXNREL.
[RxNorm overview](https://www.nlm.nih.gov/research/umls/rxnorm/overview.html)
xác nhận relationships nối ingredient, dose form, branded/unbranded products.
H67 dùng các relation này cho structured features và tạo negative đúng
ingredient nhưng sai strength/form/route.

## Điều không được suy diễn từ paper

- BERGAMOT dùng multilingual UMLS; repo này dùng WHO ICD-10 2019 và RxNorm CPC.
  Không bê checkpoint BERGAMOT và coi là đúng ontology.
- R@10 cao không có nghĩa nên output 10 candidates. H45 cho thấy Jaccard giảm
  mạnh khi k tăng; H67 mặc định cardinality 1.
- Node gần trong graph không đồng nghĩa cùng code. H44 chứng minh broad parent
  hedge làm candidate Jaccard giảm 9.5437 điểm.
- Không paper nào bảo đảm leaderboard tăng khi organizer gold bị ẩn. Vì vậy
  H67 dùng selective precision lower bound, abstention, candidate-only diff và
  giữ H38 làm fallback bất biến.

## Giả thuyết có thể bị bác bỏ

H67 chỉ được coi là có bằng chứng nếu:

- graph+hard negatives cải thiện exact-code top-1 độc lập so với synonym-only;
- context reranker tạo thêm gain trên family-held-out one-shot test;
- selective precision đạt gate với coverage vật chất;
- Turn2 chỉ thay candidates, không ảnh hưởng entity matching;
- safety audit không tái tạo H44/H58 hazards.

Nếu không đạt, kết luận đúng là ontology supervision hiện chưa đủ để thay H38,
không phải nới gate hoặc output thêm codes.
