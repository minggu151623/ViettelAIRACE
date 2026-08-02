# H41 — gán nhãn mù trên đoạn văn lặp

Mục tiêu của H41 là tạo validation độc lập, không dùng output hiện tại làm gợi
ý. Queue gồm 60 đoạn nguyên văn: 45 development và 15 holdout. Gán một đoạn một
lần sẽ áp dụng được cho 164 occurrence trong 59 hồ sơ; assertion vẫn được duyệt
riêng cho từng occurrence vì ngữ cảnh có thể khác nhau.

## Quy tắc bắt buộc

1. Không mở bất kỳ thư mục `output*`, proposal, báo cáo model hay nhãn của người
   còn lại trong lúc gán nhãn.
2. Chỉ đánh dấu đúng chuỗi được nêu trực tiếp trong văn bản. Không suy diễn một
   chẩn đoán chỉ từ triệu chứng.
3. `position=[start,end)` là offset tương đối trong đúng đoạn đang hiển thị;
   `text` phải bằng tuyệt đối `passage[start:end]`.
4. Type hợp lệ: `CHẨN_ĐOÁN`, `TRIỆU_CHỨNG`, `TÊN_XÉT_NGHIỆM`,
   `KẾT_QUẢ_XÉT_NGHIỆM`, `THUỐC`, `THÔNG_TIN_BỆNH_NHÂN`.
5. Một thực thể có thể có nhiều assertion đồng thời. Ví dụ bệnh của mẹ vừa là
   `isFamily`, vừa có thể là `isHistorical`. Chỉ dùng `isNegated`,
   `isHistorical`, `isFamily`.
6. Candidate chỉ dành cho chẩn đoán/thuốc. Nếu không chắc mã ICD-10/RxCUI thì
   để trống; không đoán và không chép từ output cũ.
7. Một đoạn không có thực thể hợp lệ vẫn phải bấm lưu giai đoạn A. Khi bảng rỗng,
   giai đoạn B tự hoàn tất.

## Tạo và kiểm tra queue

```bash
python -m airace passage-blind-prepare
python -m airace passage-queue-audit
```

Queue đã khóa tại `queue.json`, SHA-256
`a10b345aea2247cc5843e89894130f43279bd5bfc36c7bfda0c7abd357bd5f08`.

## Reviewer 1

```bash
python -m airace passage-annotate \
  --reviewer reviewer_1 \
  --out experiments/H41_repeated_passage_blind_annotation/labels/reviewer_1.jsonl
```

## Reviewer 2

Người thứ hai chạy độc lập, không mở file của reviewer 1:

```bash
python -m airace passage-annotate \
  --manifest experiments/H41_repeated_passage_blind_annotation/queue_reviewer_2.json \
  --reviewer reviewer_2 \
  --out experiments/H41_repeated_passage_blind_annotation/labels/reviewer_2.jsonl
```

Queue thứ hai chỉ chứa 15 đoạn cần double-annotation và không hiển thị tên
split. Reviewer 2 không cần gán lại cả 60 đoạn.

## Kiểm tra tiến độ

```bash
python -m airace passage-label-validate \
  --labels experiments/H41_repeated_passage_blind_annotation/labels/reviewer_1.jsonl
```

Khi hoàn tất, thêm `--require-complete`. Chỉ sau khi cả hai file hoàn tất và
được khóa checksum mới được adjudicate holdout hoặc so sánh H38 với challenger.

Sau khi khóa cả hai file, đo agreement:

```bash
python -m airace passage-reviewer-agreement \
  --primary-labels experiments/H41_repeated_passage_blind_annotation/labels/reviewer_1.jsonl \
  --secondary-labels experiments/H41_repeated_passage_blind_annotation/labels/reviewer_2.jsonl
```

Gate là strict span/type F1 ≥ 0,85 và assertion macro-Jaccard ≥ 0,80. Candidate
agreement chỉ được báo cáo chẩn đoán vì người gán nhãn được phép để trống mã khi
không chắc chắn.

## Lưu ý thống kê H42

41 occurrence trong holdout chỉ đến từ 15 passage độc lập. Không bootstrap
occurrence như 41 mẫu riêng. Sau adjudication, so sánh model phải dùng
`airace.h41_cluster_gate.evaluate_h41_passage_challenger`: scorer chỉ nhìn vùng
passage đã gán nhãn, phạt span cắt qua biên passage và bootstrap passage theo ba
strata high/middle/low. Kết quả occurrence-weighted chỉ mang tính mô tả.
