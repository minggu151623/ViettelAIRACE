# H66 — kế hoạch thuần thực thi cho Luna/Colab

## Mệnh lệnh đầu tiên

Đây là lần chạy **protocol đã khóa**, không phải phiên tiếp tục thiết kế. Đọc
toàn bộ file sau trước khi làm bất cứ điều gì:

```text
experiments/H66_marker_preserved_translation_distillation/protocol.yaml
```

Không sửa threshold/gate. Không dùng H41. Không dùng H38 hoặc Turn2 làm nhãn.
Không tạo submission nếu chưa đạt toàn bộ gate và chưa được người dùng duyệt
đúng SHA-256.

## Vì sao H66 khác H65

H65 chạy CUDA đủ nhanh nhưng chỉ có 7 mention tiếng Anh đồng thuận trên 50 câu
và không chiếu được mention nào về substring tiếng Việt. H66 không sửa tiếp
exact-string projection. Nó chuyển dịch thuật sang khâu tạo dữ liệu có nhãn:

```text
English clinical corpus có span/type
  -> marker bảo toàn thực thể
  -> dịch context và entity riêng
  -> câu tiếng Việt synthetic có offset chính xác
  -> fine-tune PhoBERT + XLM-R đọc trực tiếp tiếng Việt
  -> hiệu chỉnh trên public Vietnamese dev
  -> mở public test một lần
  -> chỉ sau khi PASS mới chạy shadow inference Turn2
```

## Trình tự bắt buộc

### 0. Bảo toàn repo

1. Clone/switch `codex/core-rebuild-h57` và pull `--ff-only`.
2. Xác minh baseline hash
   `a9b9ae07997e57080ed8ce2ad9c390f4cd8c229e8eae8de447f6f47ae6ff4d0b`.
3. Không stage notebook H65 đang có output local, `external/`, cache, model,
   dataset, `scratch/` hoặc secret.
4. Ghi commit đầu vào, GPU, CUDA, RAM và thời gian bắt đầu.

### 1. Stage 0 — inventory, tối đa 45 phút

Lập manifest cho hai English clinical corpora, hai Vietnamese public corpora,
translator và hai student. Ghi license/revision/bytes. Nếu thiếu hai English
corpus hợp lệ, thiếu ba type chung hoặc hai student không fit GPU với batch 4:
ghi `FAIL_STAGE_0` và dừng.

Không tải một corpus chỉ vì tên có vẻ phù hợp; phải đọc license/README thật.
Không commit dữ liệu hoặc checkpoint.

### 2. Stage 1 — synthetic corpus với marker

Tạo module độc lập, gợi ý:

```text
airace/marker_translation.py
airace/synthetic_clinical_corpus.py
tests/test_marker_translation.py
```

Mỗi entity có sentinel duy nhất. Dịch masked context và entity phrase riêng,
reinsert rồi lấy offset trên chính raw synthetic text. Reject mọi marker mất,
lặp, đổi thứ tự hoặc nesting sai. Split source theo document trước khi dịch.

Chạy deterministic sample 200 câu và tính đúng các gate Stage 1. Không tự sửa
câu lỗi. Nếu FAIL, ghi report rồi dừng.

### 3. Stage 2 — thí nghiệm đối chứng

Với cả PhoBERT và XLM-R, train hai arm:

- control: public Vietnamese train;
- treatment: cùng public train + synthetic.

Tối thiểu ba seed, cùng budget trong mỗi family. Chọn checkpoint/threshold chỉ
trên development. Báo macro strict span/type precision, recall, F1; per-type;
fragment rate; mean, standard deviation và từng seed.

Treatment phải thắng control đúng protocol. Nếu một student trượt, dừng trước
test và Turn2. Không chọn seed tốt nhất để che mean thất bại.

### 4. Stage 3 — public test một lần

Đóng băng decoder/threshold trước khi mở PhoNER/ViMedNER test. Chạy đúng một lần
và lưu hash prediction. Nếu bất kỳ gate nào trượt, `FAIL_STAGE_3`; không chạy
Turn2.

### 5. Stage 4 — Turn2 shadow, không sửa H38

Chạy hai student trực tiếp trên raw Vietnamese. Chỉ lấy exact same span/type
consensus qua calibration threshold. Không translation ở inference. Chỉ thêm
entity; cấm delete/replace; freeze mọi row H38. Entity mới chỉ được merge trong
scope hiện tại-khẳng định, nên assertions rỗng. Diagnosis/drug chỉ được merge
khi có đúng một candidate ontology chính thức và duy nhất; nếu không chỉ giữ
trong shadow audit. Các type còn lại có candidates rỗng.

Sinh audit một dòng mỗi proposal gồm hai confidence, span/type, record/window,
repeated-passage group, overlap H38, hazard flags, nguồn hỗ trợ và quyết định.

Nếu shadow gates FAIL: không output directory, không ZIP. Nếu PASS mới chạy
Stage 5.

### 6. Stage 5 — counterfactual risk

So additions với H58/Qwen-only và tất cả proposal bank cũ. Chạy hazard injection
trên public data. Nếu additions chủ yếu tái tạo H58 hoặc hazard rejection thấp:
dừng. Đây là bảo vệ khỏi lặp lại regression 37.7760.

### 7. Package nhưng chưa submit

Chỉ khi mọi gate PASS:

1. build `turn2/output_v22_marker_distilled` từ bản sao H38;
2. validate 100/100;
3. package hai lần và chứng minh byte-identical;
4. chạy toàn bộ tests;
5. ghi SHA-256 và execution report;
6. **không upload lên BTC** cho tới khi người dùng xem report và duyệt hash.

## Báo cáo Luna phải trả lại

Trả đúng một trong các trạng thái:

- `FAIL_STAGE_n`: gate, observed, threshold, bằng chứng, commit; không ZIP.
- `PASS_AWAITING_SUBMISSION_APPROVAL`: toàn bộ metrics, diff census, runtime,
  artifact path, SHA-256, validation và test result.

Ngoài ra phải trả lời bốn câu:

1. Synthetic treatment thắng control bao nhiêu trên dev và one-shot test?
2. Lợi ích xuất hiện ở type nào và có ổn định qua ba seed không?
3. Bao nhiêu Turn2 additions là mới thực sự, bao nhiêu trùng H58 hazards?
4. Vì sao artifact được kỳ vọng tốt hơn H38 mà không dựa vào ZIP size hay
   leaderboard feedback?

## Git cuối lượt

Stage từng file mã/report/protocol result cụ thể; không `git add .`. Không commit
dataset/checkpoint/cache/secret/notebook output H65. Commit dạng:

```text
research(results): H66 — PASS|FAIL <gate>
```

Push `codex/core-rebuild-h57` và báo commit hash.
