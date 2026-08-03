# Nhiệm vụ thực thi H64 cho model executor

## Vai trò

Bạn là executor, không thay đổi giả thuyết hoặc gate. Research lead đã khóa
protocol tại:

```text
experiments/H64_crosslingual_clinical_projection/protocol.yaml
```

Đọc đầy đủ protocol và
`literature/cross_lingual_clinical_projection.md` trước khi code. Không dùng hai
file nhãn H41; provenance của chúng đã bị vô hiệu hóa.

## Kết quả bạn phải trả lại

Một trong hai trạng thái duy nhất:

1. `FAIL`: gate nào trượt, bằng chứng định lượng, không có ZIP; hoặc
2. `PASS`: code + tests + report + output 100 JSON + ZIP deterministic; nếu đã
   submit theo ủy quyền hiện tại thì kèm hash, thời điểm và toàn bộ metric BTC.

Không trả trạng thái mơ hồ kiểu “có vẻ tốt”.

## Thứ tự thực thi bắt buộc

### 1. Đồng bộ và xác minh

```bash
cd /Users/mac/ViettelAIRACE
git switch codex/core-rebuild-h57
git pull --ff-only origin codex/core-rebuild-h57
shasum -a 256 turn2/output_v10_multiview_consensus.zip
git status --short
```

Baseline hash phải là:

```text
a9b9ae07997e57080ed8ce2ad9c390f4cd8c229e8eae8de447f6f47ae6ff4d0b
```

Không stage `external/`, `models/`, H62 cache hoặc `scratch/`.

### 2. Stage 0 — inventory và benchmark tối đa 45 phút

Tìm translator Việt↔Anh và tối thiểu hai English clinical NER model khác họ.
Ưu tiên resource đã có local; chỉ tải model khi license rõ ràng. Ghi manifest:

```text
experiments/H64_crosslingual_clinical_projection/results/resource_manifest.json
```

Mỗi resource phải có identifier, revision/digest, license, bytes, device và
nguồn. Benchmark 50 câu public end-to-end, đo thời gian và raw-span round trip.

Nếu thiếu translator, thiếu hai NER family, round trip <0.98 hoặc ETA Turn 2
>180 phút: ghi FAIL và dừng. Không chạy 100 hồ sơ.

### 3. Implement projection core

Tạo module/test riêng, không sửa H38:

```text
airace/crosslingual_projection.py
tests/test_crosslingual_projection.py
```

Core phải lưu mapping:

```text
raw Vietnamese window
 -> English translation
 -> English entities from each model
 -> entity-level back translation
 -> target candidate spans
 -> bidirectional alignment/support
 -> exact raw Vietnamese [start,end)
```

Cache theo hash của raw window + model revisions. Test tối thiểu: Unicode offset,
lặp mention, overlap, failed alignment, one-way-only rejection, type mapping,
ontology exact/ambiguous mapping, deterministic cache và repeated passages.

### 4. Stage 1 — public gold trước Turn 2

Chọn threshold/router chỉ trên PhoNER dev và ViMedNER dev nếu license cho phép.
Mở test đúng một lần. Lưu đầy đủ metrics vào execution report.

Nếu bất kỳ public-source gate trong protocol trượt: dừng, ghi analysis, không
chạy Turn 2 và không tạo ZIP.

### 5. Turn-2 inference và conservative fusion

Chỉ khi Stage 0 và 1 PASS. Chạy theo cache, báo ETA sau 15 phút. Không dùng nhiều
Ollama shard tranh cùng GPU. Sinh proposal bank có provenance cho từng span;
merge vào bản sao H38 đúng các điều kiện trong protocol.

Mọi thay đổi phải có một dòng audit gồm record, before/after, hai English model,
alignment score, back-translation, local support/ontology support và quyết định.

### 6. Gate và package

Chạy toàn bộ target-blind gates trước khi package. Nếu PASS:

```bash
python -m airace validate \
  --input turn2/input \
  --output turn2/output_v20_crosslingual_projection

python -m airace package \
  --input turn2/input \
  --output turn2/output_v20_crosslingual_projection \
  --zip turn2/output_v20_crosslingual_projection.zip

python -m airace package \
  --input turn2/input \
  --output turn2/output_v20_crosslingual_projection \
  --zip turn2/output_v20_crosslingual_projection_repeat.zip

shasum -a 256 turn2/output_v20_crosslingual_projection*.zip
unzip -t turn2/output_v20_crosslingual_projection.zip
PYTHONPATH=. pytest -q
```

Hai ZIP phải byte-identical. Xóa repeat ZIP sau khi ghi hash nếu repo convention
yêu cầu, nhưng không xóa artifact chính.

### 7. Submission và báo cáo

Chỉ submit artifact `PASS` đúng hash đã report. Không sửa ZIP sau khi hash. Sau
khi BTC chấm, ghi score tổng, WER, J_assertion, J_candidates, timestamp và ảnh
chụp vào research log/result recorder. Nếu không có quyền/session website, đưa
link ZIP cho người dùng thay vì tìm cách vượt đăng nhập.

### 8. Git

Protocol đã được research lead commit trước execution. Khi hoàn tất:

- stage từng file cụ thể, không `git add .`;
- không commit model/checkpoint/dataset/cache lớn/secret;
- commit `research(results): H64 — PASS|FAIL reason`;
- push `codex/core-rebuild-h57`;
- báo lại commit, artifact/hash hoặc gate thất bại.

## Cấm

- Không dùng H41 contaminated labels.
- Không union toàn bộ projection proposals.
- Không hạ threshold sau khi xem PhoNER/ViMedNER test hoặc leaderboard.
- Không tối ưu ZIP size.
- Không tạo candidate khi ontology match mơ hồ.
- Không submit FAIL hoặc micro-variant phát sinh sau kết quả.
