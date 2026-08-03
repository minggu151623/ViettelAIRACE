# Kế hoạch bàn giao cho model kế tiếp — Viettel AI Race Turn 2

> Đây là tài liệu thực thi, không phải danh sách ý tưởng. Model kế tiếp phải làm
> theo thứ tự, giữ nguyên các cổng dừng và không tạo submission bằng cách sửa
> ngưỡng sau khi xem kết quả. Báo cáo cho người dùng bằng tiếng Việt trực tiếp
> trong chat; không tạo HTML.

## 1. Nhiệm vụ tối cao

Tạo một challenger có bằng chứng nội bộ độc lập rằng tốt hơn baseline H38, trong
khi giữ một bản baseline có thể nộp ngay. Không tự gửi bài lên website cuộc thi;
chỉ người dùng được submit.

Thước đo chính thức đã tái tạo:

```text
score = 0.3 * (100 - WER)
      + 0.3 * J_assertion
      + 0.4 * J_candidates
```

Không có ground truth của BTC. Vì vậy leaderboard không được dùng như validation
loop và không được sinh hàng loạt micro-variant để thử mù.

## 2. Trạng thái khóa tại thời điểm bàn giao

- Repo: `/Users/mac/ViettelAIRACE`
- Nhánh làm việc: `codex/core-rebuild-h57`
- Commit bàn giao gần nhất trước file này: `f8cee88`
- Remote: `https://github.com/minggu151623/ViettelAIRACE.git`
- Baseline tốt nhất đã được BTC chấm:
  `turn2/output_v10_multiview_consensus.zip`
- Điểm baseline: `39.2813`
- SHA-256 baseline:
  `a9b9ae07997e57080ed8ce2ad9c390f4cd8c229e8eae8de447f6f47ae6ff4d0b`
- Chỉ số baseline:
  - WER: `56.1576`
  - J_assertion: `47.3920`
  - J_candidates: `29.7776`
- Backup Git: nhánh `codex/baseline-39.2813`

Các nhánh đã đóng, tuyệt đối không nộp:

- H58 section-expert recall: `37.7760`, thua mọi thành phần.
- H60 PhoNER resegmentation: sinh nhiều fragment quá ngắn.
- H61 TAPT boundary: qua source gate nhưng trượt toàn bộ target-safety gate.
- H62 assertion classifier/critic: chỉ 18/343 disagreement vượt hợp đồng
  agreement + evidence; không đủ 80 thay đổi và inference quá chậm.
- H44 mở rộng WHO parent: `35.4639`, candidate Jaccard sụt mạnh.

Các thư mục sau là dữ liệu/checkpoint cục bộ, không được `git add`:

```text
external/
models/
experiments/H62_assertion_hybrid/cache/
```

## 3. Quy tắc bất biến

1. Không sửa hoặc ghi đè H38. Mọi challenger dùng thư mục và ZIP mới.
2. Không thay đổi `turn2/input`.
3. Mọi entity phải thỏa `raw_text[start:end] == text` với offset `[start,end)`.
4. Không thêm candidate đoán mò; candidate chỉ được có ở `CHẨN_ĐOÁN` và `THUỐC`.
5. Một entity có thể có nhiều assertion đồng thời.
6. Không dùng ZIP size làm objective. H44 là phản ví dụ đã được BTC xác nhận.
7. Không chạy lại H62 toàn bộ hoặc chạy nhiều Ollama shard trên cùng GPU.
8. Không đổi gate sau khi đã nhìn holdout hoặc leaderboard.
9. Mỗi protocol phải được commit và push **trước** khi chạy thí nghiệm.
10. Chỉ tạo ZIP khi tất cả gate đã khóa đều đạt.
11. Không tự submit lên cuộc thi.
12. Mọi thay đổi có ý nghĩa phải commit và push; không commit dataset/checkpoint.

## 4. Việc đầu tiên của model kế tiếp

Chạy đúng các kiểm tra sau:

```bash
cd /Users/mac/ViettelAIRACE
git switch codex/core-rebuild-h57
git pull --ff-only origin codex/core-rebuild-h57
git status --short
shasum -a 256 turn2/output_v10_multiview_consensus.zip
unzip -t turn2/output_v10_multiview_consensus.zip
python -m airace passage-queue-audit
```

Sau đó đọc đầy đủ, theo thứ tự:

```text
NEXT_MODEL_EXECUTION_PLAN.md
research-state.yaml
findings.md
research-log.md (ít nhất từ H38 đến cuối)
experiments/H41_repeated_passage_blind_annotation/protocol.yaml
experiments/H41_repeated_passage_blind_annotation/README.md
experiments/H41_repeated_passage_blind_annotation/analysis.md
```

Nếu hash baseline hoặc input/queue không khớp, dừng challenger, báo lỗi và chỉ
giữ baseline. Không tự tái tạo queue với input khác.

## 5. Hướng nghiên cứu duy nhất được ưu tiên: H41 independent labels

Lý do: các nguồn rule/model hiện tại mang policy không tương đương; H39 chứng
minh label model không thể suy ra một latent truth chung. Các đoạn lặp bao phủ
43.07% ký tự và cho phép một nhãn độc lập được nhân sang nhiều occurrence.

Queue đã khóa:

- `queue.json`: 60 passage, 45 development + 15 holdout, 164 occurrences.
- SHA-256: `a10b345aea2247cc5843e89894130f43279bd5bfc36c7bfda0c7abd357bd5f08`.
- `queue_reviewer_2.json`: 15 passage holdout, không lộ tên split.
- SHA-256: `450cb52ca4da576709405d07e83c3c19325b837208c7353ac456bea6e3987f2d`.

### 5.1 Cách dùng model khác làm reviewer 1

Trong giai đoạn annotation, reviewer 1 chỉ được đọc:

```text
experiments/H41_repeated_passage_blind_annotation/queue.json
turn2/input/*.txt (chỉ để lấy ±200 ký tự context cho assertion)
airace/passage_annotation.py (schema/validator)
tài liệu yêu cầu chính thức
```

Reviewer 1 không được mở bất kỳ `turn2/output*`, proposal bank, cache inference,
label của reviewer khác hoặc báo cáo so sánh từng entity. Biết điểm tổng baseline
không làm mất tính mù; nhìn prediction từng hàng thì có.

Reviewer phải gán đủ 60 passage:

- Stage A trên passage nguyên văn: `text`, `type`, relative `position`, candidate.
- Stage B trên từng occurrence: assertion cho từng entity.
- Không suy chẩn đoán từ triệu chứng.
- Candidate không chắc thì để `[]`.
- Passage rỗng entity vẫn phải đánh dấu reviewed.

Output bắt buộc:

```text
experiments/H41_repeated_passage_blind_annotation/labels/reviewer_1.jsonl
```

Kiểm tra liên tục:

```bash
python -m airace passage-label-validate \
  --labels experiments/H41_repeated_passage_blind_annotation/labels/reviewer_1.jsonl

python -m airace passage-label-validate \
  --labels experiments/H41_repeated_passage_blind_annotation/labels/reviewer_1.jsonl \
  --require-complete
```

Model không được đóng đồng thời vai reviewer 1 và reviewer 2 trong cùng context,
cùng prompt hoặc cùng checkpoint. Nếu chỉ có một reviewer độc lập thì dừng ở đây
và yêu cầu cộng sự/người dùng cung cấp reviewer 2; không giả lập independence.

### 5.2 Reviewer 2

Reviewer 2 phải là người hoặc model instance độc lập, không đọc reviewer 1 và
chỉ dùng `queue_reviewer_2.json`. Output:

```text
experiments/H41_repeated_passage_blind_annotation/labels/reviewer_2.jsonl
```

Sau khi cả hai file complete, tính và ghi checksum trước khi adjudication:

```bash
shasum -a 256 \
  experiments/H41_repeated_passage_blind_annotation/labels/reviewer_1.jsonl \
  experiments/H41_repeated_passage_blind_annotation/labels/reviewer_2.jsonl

python -m airace passage-reviewer-agreement \
  --primary-labels experiments/H41_repeated_passage_blind_annotation/labels/reviewer_1.jsonl \
  --secondary-labels experiments/H41_repeated_passage_blind_annotation/labels/reviewer_2.jsonl
```

Gate cứng:

- strict span/type F1 giữa reviewers `>= 0.85`;
- assertion macro-Jaccard `>= 0.80`;
- zero schema/offset/type/assertion/candidate error.

Nếu một gate trượt: không huấn luyện, không sửa gate, không tạo ZIP.

## 6. Xây challenger sau khi label đã khóa

Tên giả thuyết tiếp theo: `H63_H41_supervised_policy_learner`.

### 6.1 Preregister trước khi code/train

Tạo:

```text
experiments/H63_h41_supervised_policy/protocol.yaml
```

Protocol phải khóa trước ít nhất:

- H38 và SHA ở mục 2.
- train = 45 development passage; holdout = đúng 15 passage đã khóa.
- Không dùng holdout để chọn feature, model, threshold, epoch hoặc decoder.
- Proposal universe là union các proposal bank đã đóng; không sinh span mới bằng
  LLM sau khi nhìn nhãn.
- Candidate head mặc định giữ nguyên H38 để tránh lặp thất bại H44.
- Record/passage grouping bắt buộc, không random-split occurrence.
- Random seed, feature list, regularization grid và tie-break.
- Một lần duy nhất mở holdout.
- Gate promotion đúng mục 6.4.

Commit và push protocol riêng:

```bash
git add experiments/H63_h41_supervised_policy/protocol.yaml
git commit -m "research(protocol): lock H63 H41 supervised policy"
git push origin codex/core-rebuild-h57
```

Không gộp protocol commit với result commit.

### 6.2 Mô hình tôi sẽ xây

Không fine-tune LLM 8B. Dùng learner nhỏ, nhanh, có thể kiểm toán:

1. **Span/type selector** trên proposal universe đóng.
   - Nhãn dương: exact `(start,end,type)` so với development annotation.
   - Nhãn âm: proposal chạm passage nhưng không exact gold.
   - Feature được phép: source-family votes, exact/overlap relations, entity
     length/shape, section, local lexical context, public-teacher confidence,
     boundary containment, type votes.
   - Không dùng leaderboard score làm feature.
   - Model: regularized logistic regression hoặc calibrated gradient boosting;
     chọn bằng leave-one-passage-out CV trên 45 development passage.
2. **Structured decoder** dùng weighted interval scheduling, giữ occurrence khác
   vị trí và cấm duplicate span/type.
3. **Assertion head** chỉ trên span đã chọn.
   - Feature: section, trigger, scope, termination, pseudo-trigger, experiencer,
     khoảng cách cue–mention và H38 assertion như một feature, không phải truth.
   - Ba binary outputs độc lập để bảo toàn multilabel.
4. **Candidate head**.
   - Lần đầu giữ nguyên candidate H38 khi exact entity còn tồn tại.
   - Entity mới chỉ nhận code khi exact normalized alias có một mapping duy nhất
     trong nguồn đã khóa; nếu không thì `[]`.
   - Không thêm WHO parent hedge diện rộng.

### 6.3 Development loop

Chỉ được tối ưu trên 45 development passage:

- leave-one-passage-out, không occurrence-level random CV;
- báo strict span/type P/R/F1;
- báo assertion Jaccard và candidate weighted Jaccard;
- so sánh H38 trong cùng passage windows;
- chọn threshold bằng objective chính thức nhưng candidate không được giảm quá
  `0.01`, assertion không được giảm quá `0.01`;
- tie-break: ít thay đổi hơn, precision cao hơn, rồi threshold cao hơn.

Không mở label hoặc report holdout trong quá trình này.

### 6.4 Holdout gate một lần

Sau khi model/threshold/decoder đã serialize và hash-lock, adjudicate holdout và
chạy `evaluate_h41_passage_challenger` đúng một lần.

Promotion chỉ khi tất cả đúng:

- strict span/type F1 challenger `>` H38;
- bootstrap 95% lower bound của final-score delta `> 0` trên 15 passage, resample
  passage trong strata, không resample 41 occurrence như độc lập;
- assertion delta `>= -0.01`;
- candidate delta `>= -0.01`;
- không span cắt qua biên passage;
- 100/100 output validate;
- ZIP lặp lại byte-identical.

Nếu fail: ghi kết quả, đóng H63, không tune theo holdout và không tạo ZIP.

## 7. Sinh output nếu và chỉ nếu H63 PASS

Challenger toàn corpus phải:

- áp model đã khóa lên toàn bộ `turn2/input`;
- giữ H38 ngoài vùng/model quyết định nếu không đủ feature;
- ghi `turn2/output_v19_h41_supervised/1.json` … `100.json`;
- validate raw offsets;
- package đúng 100 file, không file thừa;
- tạo hai ZIP độc lập và so SHA.

Lệnh tối thiểu sau khi implementation có CLI:

```bash
python -m airace validate \
  --input turn2/input \
  --output turn2/output_v19_h41_supervised

python -m airace package \
  --output turn2/output_v19_h41_supervised \
  --zip turn2/output_v19_h41_supervised.zip

python -m airace package \
  --output turn2/output_v19_h41_supervised \
  --zip turn2/output_v19_h41_supervised_repeat.zip

shasum -a 256 \
  turn2/output_v19_h41_supervised.zip \
  turn2/output_v19_h41_supervised_repeat.zip
```

Trước khi bàn giao ZIP:

```bash
unzip -t turn2/output_v19_h41_supervised.zip
unzip -Z1 turn2/output_v19_h41_supervised.zip | sort
PYTHONPATH=. pytest -q
```

Chỉ report artifact, SHA-256, số entity/thay đổi, gate report và mức rủi ro. Người
dùng tự submit.

## 8. Chế độ deadline

Mỗi job phải có checkpoint và ETA. Không để người dùng chờ nhiều giờ mà không có
artifact:

- Job inference/training dự kiến >45 phút phải cache theo record/epoch.
- Sau 15 phút đầu phải đo throughput và ETA thật.
- Nếu ETA vượt thời hạn người dùng, dừng tại checkpoint an toàn.
- Không tăng concurrency Ollama trên cùng một GPU; thử nghiệm H62 đã chứng minh
  cách đó không tăng throughput.
- Luôn giữ link baseline có thể nộp ngay:
  `/Users/mac/ViettelAIRACE/turn2/output_v10_multiview_consensus.zip`.

Nếu không thể có reviewer 2 + H63 PASS trước deadline, câu trả lời bắt buộc là:

```text
Không có challenger mới đã vượt validation độc lập. Hãy dùng baseline H38
39.2813; tôi không khuyến nghị tiêu tốn lượt nộp cho artifact chưa qua gate.
```

Không được biến deadline thành lý do phát hành output fail gate.

## 9. Git và báo cáo

- Dùng `apply_patch` để sửa file.
- Bảo toàn mọi thay đổi không liên quan của người dùng.
- `git status --short` trước mỗi commit.
- Stage từng đường dẫn cụ thể; không dùng `git add .`.
- Protocol và result là hai commit khác nhau.
- Push `codex/core-rebuild-h57` sau mỗi milestone.
- Không force-push, reset hard, checkout phá dữ liệu hoặc xóa cache rộng.
- Không commit `external/`, checkpoint, embedding cache, model weight hay secret.
- Cập nhật đồng bộ:
  - `experiments/Hxx.../protocol.yaml`
  - `experiments/Hxx.../analysis.md`
  - `findings.md`
  - `research-log.md`
  - `research-state.yaml`
- Báo cáo chat ngắn, có ETA, kết quả gate và link ZIP; không viết HTML.

## 10. Definition of done

Model chỉ được nói “đã có submission mới” khi:

1. nhãn H41 đủ và checksum-lock;
2. reviewer agreement đạt gate;
3. protocol H63 được commit trước training;
4. development chọn model mà không dùng holdout;
5. holdout mở đúng một lần và toàn bộ promotion gate đạt;
6. 100 output JSON validate;
7. hai ZIP byte-identical;
8. SHA và report được lưu;
9. code/result được commit và push;
10. model không tự submit lên website.

Nếu thiếu bất kỳ mục nào, trạng thái phải là `NOT_READY`; baseline H38 vẫn là
artifact duy nhất được khuyến nghị.
