# H67 — kế hoạch thực thi khóa cứng cho Luna trên Colab

## Mục tiêu duy nhất

Tạo một challenger **candidate-only** bằng ontology supervision thật sự. H67
không sửa entity, boundary, type, assertion hay position của H38. Nó chỉ được
đổi `candidates` của `CHẨN_ĐOÁN` và `THUỐC` sau khi vượt toàn bộ gate độc lập.

Đọc trước khi chạy:

```text
experiments/H67_ontology_exact_graph_linker/protocol.yaml
literature/h67_ontology_exact_graph_linker.md
experiments/H24_ontology_graph_classifier/README.md
experiments/H24_ontology_graph_classifier/literature_synthesis.md
```

Protocol là nguồn chân lý. File này giải thích cách thực thi, không được dùng
để nới threshold.

## Vì sao đây không phải H24 chạy lại

H24 có graph nhưng phần học có nhãn dựa vào 518 weak links của pipeline. Nó
memorize train, không generalize; model reranker chưa được fine-tune đúng task.
H67 thay ba điểm cốt lõi:

1. code identity/synonym chính thức là supervision; H38/H24 không làm gold;
2. cha, con, sibling và sản phẩm cùng ingredient nhưng sai strength/form là
   **hard negative**, không phải positive gần nghĩa;
3. model được chọn trên concept-family-held-out, sau đó mới mở Turn2 và chỉ
   làm candidate-only shadow inference.

Pipeline khóa:

```text
WHO ICD-10 2019 + RxNorm CPC 2026-07
  -> alias/code pairs + typed ontology graph
  -> sparse + Qwen3 + BGE candidate pool
  -> ontology graph adapter với exact-code margin
  -> XLM-R context reranker được fine-tune
  -> selective calibration + abstention
  -> freeze mọi field H38 trừ candidates
  -> safety audit
  -> ZIP chỉ khi toàn bộ gate PASS
```

## Quy tắc không được vi phạm

- Không dùng H38, H22, H23 hoặc H24 weak links làm nhãn train sạch.
- Không dùng leaderboard, ZIP size hoặc Turn2 distribution để chọn model hay
  threshold.
- Không mở Turn2 trước khi model, calibration threshold và action policy đã
  khóa bằng checksum.
- Không thêm WHO parent cạnh child. Không xuất raw top-k.
- Mỗi changed row chỉ có đúng một candidate mới.
- Không thay đổi bất kỳ non-candidate field nào của H38.
- Gate fail ở stage nào thì ghi report stage đó rồi dừng; không “sửa nhẹ” và
  chạy tiếp.
- Không upload lên BTC. Chỉ người dùng được submit sau khi duyệt đúng SHA-256.

## Stage 0 — preflight và bảo toàn repo, tối đa 30 phút

1. `git switch codex/core-rebuild-h57` và `git pull --ff-only`.
2. Xác minh SHA-256 H38:
   `a9b9ae07997e57080ed8ce2ad9c390f4cd8c229e8eae8de447f6f47ae6ff4d0b`.
3. Xác minh 100 JSON baseline và graph manifest H24.
4. Ghi GPU, CUDA, RAM, package/model revisions và licenses.
5. Kiểm tra forward/backward Qwen3-Embedding-0.6B adapter và XLM-R pair
   classifier trên T4 theo batch tối thiểu trong protocol.

Không commit dataset, checkpoint, embedding cache, secret, notebook output,
`external/`, `scratch/`, hoặc cache H62.

Nếu fail, trả `FAIL_STAGE_0`; không tạo aliases/model.

## Stage 1 — tạo supervision độc lập

### 1A. Tách fold trước mọi generation

- ICD: group theo category ba ký tự; cả family chỉ nằm trong một fold.
- RxNorm: group theo base ingredient/ingredient combination; mọi strength/form
  cùng ingredient family chỉ nằm trong một fold.
- Seed và tỷ lệ lấy đúng từ protocol. Lưu manifest concept IDs và checksum.

Alias không được rò từ train sang dev/test thông qua cùng family.

### 1B. RxNorm

Parse CPC chính thức:

- synonyms cùng RxCUI là positives;
- ingredient, strength, dose form, route, release type là structured fields;
- cùng ingredient nhưng sai strength/form/route là hard negatives;
- TTY được giữ làm feature và audit, không ép mọi mention về SCD.

### 1C. ICD multilingual aliases

H66 thất bại vì đo literal backtranslation của entity fragments trong câu.
H67 chỉ dịch isolated official title và đo **code identity**:

1. chạy `Helsinki-NLP/opus-mt-en-vi` và
   `facebook/nllb-200-distilled-600M` độc lập trên title;
2. giữ nguyên số, laterality và explicit negation;
3. mỗi output phải retrieve đúng source code rank-1 trong family bằng cả Qwen
   và BGE với margin tối thiểu;
4. reject nếu alias đụng nhiều code hoặc model chọn parent/sibling;
5. `Qwen/Qwen3-4B-Instruct-2507` 4-bit (nếu fit T4) chỉ được adjudicate
   disagreement, không được tự tạo gold; nếu model/revision này không tải được,
   reject disagreement thay vì đổi sang teacher tùy ý.

Lấy deterministic 300-row audit. Nếu precision code identity <0.95 hoặc các
gate số lượng/collision fail, dừng `FAIL_STAGE_1`.

### 1D. Public Vietnamese context anchors

Scan public Vietnamese corpora, không scan Turn2. Một occurrence chỉ làm
context positive nếu exact-normalized alias maps duy nhất tới một code được
accepted. Không dùng nhãn entity của H38.

## Stage 2 — frozen baselines

Tái tạo đúng năm hệ thống trong protocol và báo R@1/5/10, MRR, exact accuracy,
family confusion, ECE theo type/fold. H24 router phải reproduce. BGE chỉ được
giữ nếu bổ sung unique recall đủ gate; nếu không loại BGE **trước training**.

Đây là interface test. Không vượt gate union recall thì dừng.

## Stage 3 — huấn luyện ontology core

### Model

- Frozen multilingual node embeddings từ best Stage-2 encoder.
- Train LoRA/projection nhỏ cho mention/term encoder; không full-finetune T4 nếu
  không cần.
- Hai lớp relation-aware message passing trên graph 69,991 nodes.
- Dùng mixed precision, gradient accumulation, deterministic seed.

### Loss bắt buộc

```text
L = w1 * synonym_same_code
  + w2 * term_to_own_node
  + w3 * true_vs_corrupted_subgraph_DGI
  + w4 * typed_relation_prediction
  + w5 * exact_code_hard_negative_margin
```

Không dùng parent-child attraction loss. Parent/child/sibling là exact-code
hard negatives. Với RxNorm, cùng ingredient nhưng sai strength/form/route cũng
là hard negative.

Chạy ablation A/B/C/D và ba seed đúng protocol. Chọn bằng mean dev, rồi mở test
một lần. Nếu graph hoặc hard-negative không tạo gain độc lập: `FAIL_STAGE_3`.

## Stage 4 — fine-tune context reranker và calibration

Reranker chỉ xem top-20 pool đã khóa. Input phải có local context, marked
mention, type, concept name/path và structured drug fields. Train trên official
synonyms, public exact anchors và online hard negatives; tuyệt đối không train
trên H38/Turn2 predictions.

Chạy ba ablation:

1. graph score;
2. context không graph;
3. context + graph + drug structure.

Calibrate trên dev, khóa threshold và checksum trước test. Có hai action riêng:

- `FILL_EMPTY`: lower 95% precision bound >=0.95 và >=3 views đồng thuận;
- `REPLACE`: lower 95% bound >=0.90, mọi sparse/dense/graph/context view chọn
  cùng new code, và pairwise score chứng minh old code thua.

Model được phép `ABSTAIN`. Không đạt coverage/precision/calibration gate thì
dừng trước Turn2.

## Stage 5 — Turn2 shadow candidate-only

Chỉ bây giờ mới đọc Turn2. Trước inference ghi hash model, index, thresholds và
action-policy config.

Clone H38 in-memory rồi áp dụng duy nhất ba action `UNCHANGED`, `FILL_EMPTY`,
`REPLACE`. Cấm parent addition, deletion-only và top-k. Mỗi diff record phải
có:

```json
{
  "record": 1,
  "entity_key": [0, 10, "CHẨN_ĐOÁN"],
  "mention": "...",
  "old_candidates": [],
  "new_candidates": ["..."],
  "action": "FILL_EMPTY",
  "view_top1": {},
  "top1_margin": 0.0,
  "calibrated_probability": 0.0,
  "ontology_evidence": {},
  "decision": "ACCEPT|REJECT"
}
```

Diff semantic, không diff whitespace JSON. Assert exact equality cho text,
type, position, assertions, entity order và entity count. Nếu changed rows,
record breadth, type breadth, family concentration hoặc cardinality gate fail:
`FAIL_STAGE_5`, không ZIP.

## Stage 6 — safety audit và package

Chạy các hazard:

- ICD parent/child/sibling;
- cùng bệnh nhưng khác nguyên nhân/vị trí/mức độ;
- RxNorm đúng ingredient nhưng sai strength/form/route/release;
- alias collision, acronym và numeric ambiguity;
- H44 broad-parent rows và H58 entity-matching hazards.

Official PDF examples chỉ là untouched sanity set. H24 weak links chỉ là
secondary diagnostic, không được quyết định promotion.

Nếu toàn bộ gate PASS:

1. tạo `turn2/output_v23_ontology_exact_linker`;
2. validate 100/100;
3. package hai lần và chứng minh byte-identical;
4. chạy full tests;
5. ghi exact SHA-256 và execution report;
6. không submit.

## Báo cáo Luna phải trả

Một trong hai dạng duy nhất:

```text
FAIL_STAGE_n
- observed vs threshold
- ablation/fold/seed gây fail
- artifact đã xóa hoặc không tạo
- H38 vẫn an toàn
- commit hash
```

hoặc:

```text
PASS_AWAITING_SUBMISSION_APPROVAL
- independent dev/test metrics của A/B/C/D/full
- selective precision, coverage, ECE
- Turn2 FILL/REPLACE census theo type/family/record
- non-candidate identity proof
- validation/tests/determinism
- ZIP path + SHA-256 + size
- commit hash
```

Ngoài ra trả lời rõ:

1. Gain đến từ synonym, graph, hard negatives hay context?
2. Graph giảm bao nhiêu parent/child/sibling errors?
3. Bao nhiêu changed rows là fill và bao nhiêu là replacement?
4. Tại sao challenger có cơ sở tăng candidate Jaccard mà không lặp H44?

## Thời gian và checkpoint

Mỗi stage ghi heartbeat tối thiểu 20 phút/lần. Ước lượng T4:

- Stage 0: 30 phút;
- Stage 1: 60–120 phút;
- Stage 2: 30–60 phút;
- Stage 3: 2–4 giờ;
- Stage 4: 1–3 giờ;
- Stage 5–6: 45–90 phút.

Không dùng timeout tổng. Dừng ngay khi một locked gate fail.

## Git

Stage file cụ thể; không `git add .`. Commit format:

```text
research(results): H67 PASS|FAIL Stage <n> — <gate>
```

Push `codex/core-rebuild-h57`. Không push dataset/checkpoint/cache/secret hay
notebook output.
