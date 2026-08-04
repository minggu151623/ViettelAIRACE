# Kế hoạch thực thi cho Luna — H68 RxNorm Exact Drug Linker

## 0. Mục tiêu và giới hạn

Đây là kế hoạch worker đã khóa, không phải danh sách ý tưởng. Luna phải chạy
theo stage, ghi report ở cuối từng stage và dừng ngay khi gate trượt. Không được
đổi threshold sau khi thấy dev, test, Turn2 hay leaderboard.

Mục tiêu H68 là tận dụng phần duy nhất của H67 đã có bằng chứng độc lập mạnh:
71.065 alias RxNorm cùng mã và 34.291 family. H68 chỉ sửa `candidates` của entity
`THUỐC`. Mọi span, type, offset, assertion, thứ tự, số entity và toàn bộ ICD của
H38 phải bất biến.

H68 không được quảng cáo như một nhánh chắc chắn tăng 10 điểm. Nó là challenger
ít coupling nhất còn khả thi trong thời gian cuối: nếu pass, nó có cơ sở tăng
`J_candidates` mà không làm hỏng WER/assertion; nếu fail, H38 vẫn nguyên vẹn.

Protocol bắt buộc phải đọc đầy đủ:

```text
experiments/H68_rxnorm_exact_drug_linker/protocol.yaml
```

## 1. Trạng thái khóa

- Repo local: `/Users/mac/ViettelAIRACE`
- Nhánh: `codex/core-rebuild-h57`
- Baseline: `turn2/output_v10_multiview_consensus.zip`
- SHA-256: `a9b9ae07997e57080ed8ce2ad9c390f4cd8c229e8eae8de447f6f47ae6ff4d0b`
- Điểm: `39.2813`
- Baseline có 276 entity thuốc: 201 candidate nonempty, 75 empty.
- H67 đã fail vì ICD, nhưng RxNorm pass: 71.065 alias và 856 public anchor tất
  cả type. Không chạy lại ICD translation và không hạ gate H67.
- Không tự submit. Chỉ tạo artifact `PASS_AWAITING_SUBMISSION_APPROVAL`.

Không stage/commit các đường dẫn bẩn có sẵn:

```text
H65_Colab_Stage0.ipynb
experiments/H62_assertion_hybrid/cache/
external/PhoNER_COVID19/
external/ViMQ/
external/ViMedNer/
scratch/
```

## 2. Preflight bắt buộc ở local

```bash
cd /Users/mac/ViettelAIRACE
git switch codex/core-rebuild-h57
git pull --ff-only origin codex/core-rebuild-h57
git status --short
shasum -a 256 turn2/output_v10_multiview_consensus.zip
python -m airace validate --input turn2/input --output turn2/output_v10_multiview_consensus
```

Đọc theo thứ tự:

```text
research-state.yaml
findings.md (H38, H44, H45, H58, H67)
experiments/H67_ontology_exact_graph_linker/results/stage_0_report.json
experiments/H67_ontology_exact_graph_linker/results/stage_1_report.json
experiments/H67_ontology_exact_graph_linker/run_stage_1_colab.py
experiments/H68_rxnorm_exact_drug_linker/protocol.yaml
```

Nếu hash hoặc census 276/201/75 không khớp: `FAIL_STAGE_0`, không chạy Colab.

## 3. Quy tắc vận hành Colab để không lặp lỗi cũ

Tạo runner Python theo stage, không đặt toàn bộ thí nghiệm vào một cell/command
hai giờ. Mỗi runner phải:

1. dùng `set -euo pipefail` ở shell wrapper và propagate nonzero exit;
2. ghi `stage_n_report.json` kể cả khi exception;
3. lưu manifest/checkpoint nhỏ sau mỗi stage vào repo hoặc thư mục đồng bộ;
4. kiểm tra file tồn tại trước khi đọc report;
5. dùng trực tiếp `AutoTokenizer`/`AutoModel`, không dùng legacy
   `pipeline("translation")`;
6. resolve và ghi immutable model revision trước download;
7. ghi Python, CUDA, PyTorch, Transformers, GPU, seed và elapsed time;
8. không giả định cache của runtime H67 còn tồn tại;
9. không dùng timeout tổng; gate fail thì dừng ngay;
10. heartbeat ngắn sau mỗi 20 phút hoặc mỗi stage.

Tên file Luna phải tạo:

```text
experiments/H68_rxnorm_exact_drug_linker/run_stage_0_colab.py
experiments/H68_rxnorm_exact_drug_linker/run_stage_1_colab.py
experiments/H68_rxnorm_exact_drug_linker/run_stage_2_colab.py
experiments/H68_rxnorm_exact_drug_linker/run_stage_3_colab.py
experiments/H68_rxnorm_exact_drug_linker/run_stage_4_colab.py
experiments/H68_rxnorm_exact_drug_linker/run_stage_5_local.py
experiments/H68_rxnorm_exact_drug_linker/prepare_and_run_colab.py
experiments/H68_rxnorm_exact_drug_linker/results/
```

## 4. Stage 0 — integrity/CUDA

Tái sử dụng logic H67 Stage 0 nhưng chỉ inventory CPC. Download đúng snapshot
`RxNorm_full_prescribe_07062026.zip`; subset CPC của NLM không cần UMLS license.

Gate đầy đủ nằm trong protocol. Ngoài hash, validation và census, phải smoke
test Qwen3 Embedding 0.6B và XLM-R batch 8 trên CUDA. Report:

```text
results/stage_0_report.json
```

Không tải/training ICD, Opus hay NLLB.

## 5. Stage 1 — dataset RxNorm độc lập

Parse `RXNCONSO.RRF`, `RXNREL.RRF`, `RXNSAT.RRF`:

- chỉ active CPC/RXNORM, `SUPPRESS=N`;
- giữ TTY và RxCUI;
- dựng quan hệ ingredient, brand, strength, dose form và product;
- group split trước theo base ingredient/ingredient combination;
- mọi product/brand/strength/form cùng family ở đúng một fold;
- cùng RxCUI là positive; code gần nhưng khác strength/form/route là negative;
- không dùng H38/H24 làm clean label.

Sinh deterministic Vietnamese/clinical renderings chỉ bằng phép chuẩn hóa bảo
toàn cấu trúc: đơn vị, số thập phân, `/`, `mỗi`, route (`po/uống`, `iv/tĩnh
mạch`, `im/bắp`, `sc/dưới da`) và lịch dùng. Không dịch hay phát minh ingredient.
Mọi rendering phải round-trip về đúng RxCUI.

Scan public corpora đã có để lấy exact unique anchors, nhưng chỉ RxNorm. Split
theo document trước. Nếu dưới 300 anchor hoặc collision vượt 0,2%, dừng.

Artifacts nhỏ có thể commit: manifest, counts, checksums, report. Không commit
RRF, embeddings hay generated dataset lớn.

## 6. Stage 2 — retrieval và structured parser

Xây bốn view độc lập:

1. exact normalized alias hash;
2. char 2–5 gram TF-IDF;
3. Qwen3 Embedding 0.6B;
4. structured matcher ingredient/strength/form/route/release.

BGE-m3 chỉ được giữ nếu thêm ít nhất 1 điểm unique dev R@20. Không giữ model chỉ
vì “ensemble nhiều model”. Candidate union tối đa top-20 cho reranker, nhưng
output cuối luôn singleton.

Parser tuyệt đối không được bỏ qua số. Nếu mention ghi 25 mg mà candidate 50 mg,
đó là contradiction và candidate phải bị loại. Thiếu strength có thể abstain,
không được đoán product.

Chạy đúng gate Stage 2 trong protocol. Fail thì không train reranker.

## 7. Stage 3 — pairwise reranker có hard negatives

Luna được chọn XLM-R LoRA hoặc MLP trên frozen embeddings dựa trên smoke test,
nhưng phải khóa lựa chọn trước test. Train ba seed `68, 680, 6800`.

Các ablation bắt buộc:

```text
A = retriever
B = A + structured fields
C = B + pairwise reranker
D = C + online same-family hard negatives
```

Hard negatives phải gồm:

- đúng ingredient, sai strength;
- đúng ingredient, sai dose form;
- đúng ingredient, sai route/release;
- brand đúng so với generic/brand gần nhưng sai;
- lexical nearest wrong RxCUI.

Chọn model/epoch trên dev mean ba seed; mở test đúng một lần. Không đạt gain
khóa thì `FAIL_STAGE_3`.

## 8. Stage 4 — selective calibration

Calibrate chỉ trên family-held-out dev. Dùng Wilson lower 95% bound, không dùng
accuracy point estimate để tự tin giả.

- `FILL_EMPTY`: exact+sparse+Qwen+structured cùng code, không contradiction,
  lower bound >=0,95.
- `REPLACE`: mọi retained view cùng code, old code thua pairwise, mọi explicit
  field match, lower bound >=0,92.

Khóa byte checksum của model, indexes, threshold và action policy trước khi
đọc `turn2/input` hoặc H38 rows. Gate fail thì dừng.

## 9. Stage 5 — Turn2 shadow inference

Chỉ Stage 0–4 đều pass mới mở Turn2/H38. Clone H38 in-memory rồi chỉ thay
candidate của `THUỐC` bằng ba action `UNCHANGED/FILL_EMPTY/REPLACE`.

Mỗi proposal phải ghi sidecar:

```json
{
  "record": 1,
  "entity_key": [53, 75, "THUỐC"],
  "mention": "metoprolol 25mg po bid",
  "old_candidates": ["..."],
  "new_candidates": ["..."],
  "action": "REPLACE",
  "view_top1": {},
  "explicit_fields": {},
  "candidate_fields": {},
  "contradictions": [],
  "pairwise_margin_vs_old": 0.0,
  "calibrated_probability": 0.0,
  "decision": "ACCEPT"
}
```

Semantic diff phải chứng minh:

- zero non-candidate diff;
- zero ICD candidate diff;
- changed rows 15–120, ít nhất 8 record và 10 normalized mentions;
- mỗi changed list đúng một active RxCUI;
- không một RxCUI chiếm quá 20% changes;
- 100/100 JSON validate.

Nếu materiality fail, không tạo ZIP. Không mở rộng bằng row confidence thấp để
đủ số lượng.

## 10. Stage 6 — package và báo cáo

Nếu pass:

```text
turn2/output_v23_rxnorm_exact_drug_linker/
turn2/output_v23_rxnorm_exact_drug_linker.zip
```

Package hai lần, byte-identical, ZIP chứa đúng `output/1.json`–`100.json`.
Chạy full tests. Không submit.

Luna trả đúng một trong hai dạng:

```text
FAIL_STAGE_n
- observed vs gate
- fold/seed/ablation gây fail
- artifact nào không tạo hoặc đã xóa
- H38 còn nguyên
- commit hash
```

hoặc:

```text
PASS_AWAITING_SUBMISSION_APPROVAL
- Stage 2/3 metrics và ablations
- selective precision lower bound, coverage, ECE
- FILL/REPLACE census theo record/mention/RxCUI
- proof zero non-candidate và zero ICD diff
- validation/tests/determinism
- ZIP absolute path, bytes, SHA-256
- commit hash
```

Phải trả lời thêm:

1. Gain offline đến từ retrieval, structured parser hay hard negatives?
2. Có bao nhiêu lỗi wrong strength/form/route được loại?
3. Bao nhiêu fill, bao nhiêu replace và bao nhiêu abstain?
4. Tại sao H68 không lặp H44/H45?
5. Nếu không đủ 15 change, bằng chứng nào cho thấy nên giữ H38?

## 11. Git

Protocol đã phải được commit riêng trước execution. Khi chạy, stage file cụ thể;
không `git add .`. Không commit dataset/checkpoint/cache/secret/notebook output.

Commit kết quả từng mốc:

```text
research(implementation): add H68 Stage <n> runner
research(results): H68 PASS|FAIL Stage <n> — <gate>
```

Push `codex/core-rebuild-h57` sau mỗi mốc có ý nghĩa. Không sửa lịch sử H67.
