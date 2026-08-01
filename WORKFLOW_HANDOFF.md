# Viettel AI Race — tài liệu bàn giao workflow

## 0. Giải thích thuật ngữ bằng ngôn ngữ đơn giản

- **Entity / thực thể**: một khái niệm y khoa cần lấy ra khỏi văn bản, ví dụ
  `đau ngực`, `hen suyễn`, `metoprolol 25mg`.
- **Span**: đoạn chữ nguyên văn đại diện cho một entity. Ví dụ span của
  `đau ngực` không được đổi thành `chest pain` hoặc viết lại thành câu khác.
- **Offset / position**: vị trí bắt đầu và kết thúc của span trong văn bản gốc.
  `[10, 18]` nghĩa là lấy các ký tự từ vị trí 10 đến trước vị trí 18.
- **Regex**: “mẫu tìm kiếm” bằng ký hiệu. Ví dụ regex
  `\d+\s*mg` tìm các chuỗi như `25mg`, `25 mg`, `500 mg`; nó không hiểu y khoa,
  chỉ nhận ra hình dạng của chuỗi.
- **Lexicon / từ điển chuyên ngành**: danh sách các từ/cụm từ đã biết trước,
  ví dụ danh sách thuốc, tên bệnh, triệu chứng và xét nghiệm. Lexicon giúp bắt
  chính xác các cụm quen thuộc nhưng không tự biết cách diễn đạt mới.
- **Detector**: bộ phát hiện entity. Trong workflow cũ, detector chủ yếu dùng
  regex + lexicon; trong workflow mới, Qwen đề xuất thêm entity rồi detector
  và rule bổ sung/kiểm tra.
- **Type**: loại của entity, gồm `CHẨN_ĐOÁN`, `TRIỆU_CHỨNG`, `THUỐC`,
  `TÊN_XÉT_NGHIỆM`, `KẾT_QUẢ_XÉT_NGHIỆM`, `THÔNG_TIN_BỆNH_NHÂN`.
- **Assertion**: trạng thái/ngữ cảnh của entity:
  `isHistorical` = thuộc tiền sử, `isNegated` = bị phủ định,
  `isFamily` = thuộc người nhà bệnh nhân.
- **Candidate**: mã chuẩn có thể tương ứng với entity. Bệnh dùng mã ICD-10;
  thuốc dùng RxCUI của RxNorm. Candidate không phải là tên entity.
- **Candidate resolver**: bộ tra cứu và chọn mã candidate từ database local.
  Nó không phát hiện entity; nó chỉ trả lời “entity này có mã chuẩn nào?”.
- **Grounding**: kiểm tra entity do model đề xuất có thật sự là substring trong
  input hay không, rồi tính offset chính xác bằng code. Grounding ngăn model
  viết lại hoặc bịa vị trí.
- **Occurrence**: một lần xuất hiện cụ thể. `đau ngực` xuất hiện ba lần thì
  có thể có ba occurrence với ba position khác nhau.
- **Overlap**: hai entity dùng chung một phần ký tự. Ví dụ
  `đau ngực` và `cảm giác đau ngực vùng trước tim`.
- **Sanitizer**: bộ lọc hậu xử lý để loại lỗi dễ nhận biết, ví dụ loại
  `thủ thuật can thiệp` nếu model gán nhầm thành thuốc.
- **Validator**: bộ kiểm tra cuối trước khi đóng gói: JSON hợp lệ, type hợp lệ,
  offset đúng, không trùng record và `raw_text[start:end] == text`.
- **Recall**: bắt được bao nhiêu entity đúng. Recall thấp nghĩa là bỏ sót nhiều.
- **Precision**: trong các entity đã bắt, có bao nhiêu entity thực sự đúng.
  Precision thấp nghĩa là sinh nhiều entity rác.
- **WER**: mức sai khác của text/span. WER càng cao thì text score càng thấp.
- **Jaccard**: mức giao nhau giữa hai tập assertion hoặc candidate. Candidate
  thừa cũng làm Jaccard giảm.

## 1. Kết luận ngắn

Hai submission cũ đều là pipeline rule/dictionary. Chúng tạo JSON hợp lệ nhưng
điểm leaderboard chỉ khoảng `0.3380`–`0.3690` trên thang 100. Nguyên nhân
chính không phải ZIP hay định dạng, mà là recall/span của bộ từ điển quá thấp
so với hidden gold; chỉnh vài candidate không thể sửa lỗi đó.

Workflow hiện tại chuyển sang mô hình lai:

```text
input/*.txt
  -> Qwen3 8B chạy local qua Ollama (đề xuất khái niệm)
  -> grounding exact trên raw_text (code tự tìm offset)
  -> mở rộng mọi occurrence của cùng text/type
  -> assertion cục bộ bằng rule
  -> rule/dictionary bổ sung thuốc và xét nghiệm chắc chắn
  -> ICD/RxNorm resolver local
  -> sanitizer chống span/type lỗi
  -> validator
  -> output/*.json
  -> package ZIP
```

Workflow đã hoàn tất 100 hồ sơ và chưa được nộp leaderboard.

Lượt chấm gần nhất của Qwen hybrid là `1.3060` (WER `99.9611`,
J_assertion `2.5774`, J_candidates `1.3028`). Đây là cải thiện thật so với
`0.3690`, nhưng WER gần như không cải thiện; vì vậy thêm candidate hoặc đổi
ngưỡng RxNorm không giải quyết được nút thắt chính.

## 2. Workflow cũ: rule/dictionary baseline

Các module chính:

- `airace/detector.py`: regex và lexicon để tìm thuốc, triệu chứng, chẩn đoán,
  tên/kết quả xét nghiệm.
- `airace/assertions.py`: suy luận `isHistorical`, `isNegated`,
  `isFamily` theo section, dòng và câu cục bộ.
- `airace/candidates.py`: map ICD local và RxNorm CPC local; chọn top-1,
  tránh candidate thừa.
- `airace/validator.py`: kiểm UTF-8, type/assertion, offset `[start,end)`,
  thứ tự và trùng entity.
- `airace/package_output.py`: đóng gói đúng `output/1.json`–`output/100.json`.

Các profile đã thử:

| Profile | Ý tưởng | Kết quả đã nhận |
|---|---|---:|
| baseline | rule/dictionary gốc | `0.3690` |
| precision | giảm false positive, đổi candidate | `0.3380` |
| baseline_strength | giữ span cũ, chỉ thêm candidate thuốc có liều | `0.3690` |
| recall/section_only | thêm span theo section | chưa dùng để kết luận; không nên thử mù tiếp |

Điểm chung: WER hiển thị khoảng `99.95`, assertion khoảng `0.90`, candidate
chỉ `0.13`–`0.19`. Điều đó cho thấy nhiều entity rule không được ghép với gold
ẩn. Vì BTC không cung cấp ground truth, không thể tune threshold theo điểm
thật; nộp thêm các biến thể nhỏ chỉ tiêu tốn lượt.

## 3. Workflow hiện tại: Qwen3 8B + rule hybrid

### 3.1 Model

- Model local: `qwen3:8b`, đã tải trong Ollama, khoảng 5.2 GB.
- Chạy offline qua `http://127.0.0.1:11434/api/chat`; inference không gọi API
  ICD/RxNorm ngoài.
- Qwen chỉ đề xuất khái niệm, type, assertion sơ bộ và ICD khi chắc chắn.
- Prompt yêu cầu span nguyên văn, không biến thủ thuật thành thuốc, không biến
  triệu chứng thành chẩn đoán, và span phải gọn.

### 3.2 Grounding và occurrence

Offset do model sinh trước đây không đáng tin, đặc biệt với văn bản Unicode và
chuỗi lặp. Vì vậy prompt hiện tại yêu cầu model chỉ trả mỗi cặp
`(text, type)` một lần, không trả `start`.

Code sau đó:

1. tìm mọi substring chính xác trong `raw_text`;
2. tạo một entity riêng cho mỗi occurrence;
3. giữ `raw_text[start:end] == text`;
4. gọi assertion engine lại theo vị trí thật.

Cách này đã loại lỗi model tự bịa các offset tăng đều ngoài độ dài văn bản.

### 3.3 Hậu kiểm sanitizer

`airace/llm_inference.py` đang lọc các lỗi có quy luật:

- cắt thuốc trước `điều trị`, `cho`, `do`, `nhằm`;
- giữ suffix lịch dùng `:prn`;
- loại `thủ thuật can thiệp`, `đặt shunt`, `dẫn lưu` khỏi THUỐC/XÉT_NGHIỆM;
- đổi analyte bị gán nhầm KẾT_QUẢ thành TÊN_XÉT_NGHIỆM;
- loại số thứ tự section bị gán thành kết quả;
- loại risk/social phrase như `rượu bia`, `cà phê`, `mất việc làm` khỏi
  TRIỆU_CHỨNG;
- loại `hút thuốc` khi bị gán nhầm THÔNG_TIN_BỆNH_NHÂN;
- tách các cụm symptom lexicon như `lo âu mất ngủ`;
- bỏ span dài kiểu câu hoàn chỉnh nuốt nhiều xét nghiệm;
- loại overlap cùng type theo quy tắc compact/longest span.

### 3.4 Candidate và assertion

- CandidateResolver vẫn là local ICD/RxNorm; không bịa candidate khi không có
  bằng chứng.
- Curated mapping được ưu tiên trước catalog rộng, ví dụ nystatin không bị
  catalog đổi sang RxCUI khác khi mention không có mapping strength cụ thể.
- Assertion được tính lại sau khi grounding. Section `Tiền sử bệnh hiện tại`
  không được coi là lịch sử.

## 4. Workflow V3: consensus + token classifier

V1 trainer trước đây có ba lỗi cấu trúc: dùng tokenizer chậm, chỉ nhìn 224
token đầu hồ sơ, và không có validation. V3 đã thay bằng:

- `airace/silver.py`: kết hợp Qwen, rule/dictionary và BamiBERT-ViMedNER;
  teacher chỉ giúp siết span/type, không tự quyết định thuốc/candidate.
- `labels/manual_validation.jsonl`: 9 hồ sơ/40 thực thể đã được rà soát thủ
  công, dùng làm holdout độc lập.
- `airace/train.py`: tokenizer nhanh, cửa sổ 256 token overlap 64, BIO
  token-classification, validation strict span/type F1, early stopping, hỗ
  trợ CUDA/MPS/CPU.
- `airace/review.py`: đo strict span/type precision/recall/F1 và tái hiện
  ba thành phần metric trên holdout.
- `airace/annotation_app.py`: bảng chỉnh span/type/start/end/assertions/
  candidates, tự kiểm tra `raw_text[start:end]`.
- `airace/assertions.py`: scope phủ định cục bộ; không coi “không do”, “không
  xác định”, “không đặc hiệu” là phủ định chẩn đoán.

Qwen trên holdout thủ công hiện đạt strict span/type F1 `0.8444`; đó là cổng
so sánh nội bộ, không phải ground truth của BTC. Chỉ dùng checkpoint V3 để
đóng gói khi nó không kém cổng này.

## 5. Trạng thái hiện tại

- Thư mục ứng viên: `output_qwen3_hybrid/`
- Đã sinh và validate: 100 JSON.
- Đã tạo: `output_qwen3_hybrid.zip`.
- Report: `reports/qwen3_hybrid.json`.
- Thời gian sinh Qwen ban đầu: khoảng 2.943,6 giây; các lần resume sau đó
  chỉ chạy sanitizer/resolver trên JSON đã có.
- Ollama model đã được unload để giải phóng GPU/RAM; model vẫn cài local.
- 12 unit test hiện có vẫn pass.
- Checkpoint XLM-R VietMed-NER đã tải vào Hugging Face cache để khảo sát,
  nhưng chưa đưa vào pipeline nộp vì test nhanh cho thấy nó hay gán procedure/
  section heading sai loại. Không được tự động trộn model này vào output.
- BamiBERT-ViMedNER là teacher mới; model card công bố các nhãn bệnh, triệu
  chứng và biện pháp chẩn đoán tiếng Việt. Nhãn điều trị của nó vẫn bị bỏ qua
  để tránh nhầm thủ thuật thành thuốc.

## 6. Cách tiếp tục

Từ thư mục project, chạy lại đúng lệnh sau:

```bash
cd /Users/mac/ViettelAIRACE
ollama run qwen3:8b
```

Giữ Ollama server hoạt động, mở terminal khác:

```bash
PYTHONPATH=. /opt/anaconda3/bin/python3 -u -m airace llm-infer \
  --input input \
  --output output_qwen3_hybrid \
  --report reports/qwen3_hybrid.json \
  --model qwen3:8b
```

Lệnh có resume: các file JSON đã tồn tại sẽ được đọc lại, resolve candidate và
sanitize theo code mới; các file còn thiếu mới gọi Qwen. Không dùng
`--no-resume` trừ khi muốn tái sinh toàn bộ.

Sau khi đủ 100 file:

```bash
PYTHONPATH=. /opt/anaconda3/bin/python3 -m airace validate \
  --input input --output output_qwen3_hybrid

PYTHONPATH=. /opt/anaconda3/bin/python3 -m airace package \
  --input input \
  --output output_qwen3_hybrid \
  --zip output_qwen3_hybrid.zip

unzip -l output_qwen3_hybrid.zip | tail
```

Validator hiện đã pass và ZIP có đúng 100 member. Vẫn cần kiểm tra thủ công
một số file dài/ngắn trước khi cân nhắc lượt nộp cuối; không có cam kết điểm
leaderboard vì hidden ground truth không được cung cấp.

## 7. Lệnh V3

```bash
python -m airace prepare-silver \
  --qwen output_qwen3_hybrid \
  --teacher cbc-528a/BamiBERT-ViMedNER \
  --output labels/silver_consensus.jsonl \
  --holdout-labels labels/manual_validation.jsonl \
  --consensus-output output_v3_consensus

python -m airace train \
  --labels labels/silver_consensus.jsonl \
  --validation-labels labels/manual_validation.jsonl \
  --base-model cbc-528a/BamiBERT-ViMedNER \
  --output models/bami-airace-v3

python -m airace infer --input input --output output_v3_token \
  --model-checkpoint models/bami-airace-v3 \
  --report reports/v3_token.json

python -m airace review-evaluate \
  --labels labels/manual_validation.jsonl --pred output_v3_token
```

## 8. Các điểm cần đánh giá trước khi nộp

1. **Recall/span**: Qwen phải tìm được concepts mà baseline bỏ sót, nhưng không
   kéo cả câu vào span.
2. **Assertion**: đặc biệt phân biệt `Tiền sử bệnh` với `Bệnh sử hiện tại`,
   và phủ định của symptom/result.
3. **Candidate Jaccard**: chỉ top-1 local khi đủ chắc; candidate thừa bị phạt.
4. **Runtime**: Qwen 8B local có thể mất khoảng 15–90 giây tùy hồ sơ. Nếu
   vòng chấm chạy source với giới hạn 600 giây thì workflow cần được chưng cất
   thành lexicon/rule hoặc model encoder nhanh; nếu chỉ upload ZIP output thì
   thời gian sinh offline không ảnh hưởng điểm.
5. **Không có GT**: mọi điểm leaderboard vẫn là ẩn. Internal fixture chỉ kiểm
   format, offset và logic; không được coi là ước lượng điểm thật.

## 9. Những file quan trọng

- `airace/llm_inference.py`: Qwen request, grounding, occurrence expansion,
  merge và sanitizer.
- `airace/assertions.py`: scope assertion.
- `airace/candidates.py`: ICD/RxNorm resolver local.
- `airace/metrics.py`: evaluator nội bộ; đã sửa lỗi xử lý `candidates=None`.
- `airace/validator.py`: validator submission.
- `airace/silver.py`: teacher và consensus labels.
- `airace/train.py`: sliding-window BIO trainer và inference.
- `airace/review.py`: holdout evaluator.
- `reports/`: báo cáo các run cũ và run Qwen khi hoàn tất.
- `WORKFLOW_HANDOFF.md`: tài liệu bàn giao này.
