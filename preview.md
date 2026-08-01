# Tóm tắt trao đổi: Viettel AI Race — chuẩn hóa thực thể y khoa

## 1. Bối cảnh và mục tiêu

Mục tiêu là xây dựng hệ thống xử lý văn bản y khoa cho bài Viettel AI Race. Hệ thống cần phát hiện các thực thể, phân loại loại thực thể, xác định trạng thái/ngữ cảnh và ánh xạ sang mã chuẩn.

Các trường đầu ra quan trọng:

- `text`: span nguyên văn trong văn bản.
- `type`: loại thực thể, ví dụ `CHẨN_ĐOÁN`, `THUỐC`, `TRIỆU_CHỨNG`, `XÉT_NGHIỆM`.
- `candidates`: danh sách mã ICD hoặc RxNorm tiềm năng.
- `assertions`: trạng thái như `isNegated`, `isFamily`, `isHistorical`.
- `position`: vị trí `[start, end)` trong văn bản gốc.

Hai bài toán chính là:

1. ICD linking cho bệnh/chẩn đoán.
2. RxNorm linking cho thuốc.

Phát hiện đúng tên bệnh hoặc thuốc mới chỉ là nửa đầu; phần khó là chọn đúng mã và mức độ cụ thể dựa vào ngữ cảnh.

---

## 2. ICD và RxNorm khác nhau như thế nào?

| Khía cạnh | ICD | RxNorm |
|---|---|---|
| Đối tượng | Bệnh, chẩn đoán | Thuốc/concept thuốc |
| Câu hỏi | Bệnh này chuẩn hóa thành mã nào? | Thuốc này chuẩn hóa thành RxCUI nào? |
| Thông tin cần dùng | Tên bệnh, vị trí, biến chứng, nguyên nhân, mức độ | Hoạt chất, hàm lượng, đơn vị, dạng thuốc, đường dùng, giải phóng |
| Khó khăn | Chọn đúng nhánh mã cụ thể | Phân biệt các concept có hàm lượng/dạng khác nhau |
| Assertion | Thông tin ngữ cảnh độc lập với mã | Thông tin ngữ cảnh độc lập với RxCUI |

Ví dụ:

```json
{
  "text": "trào ngược dạ dày–thực quản",
  "type": "CHẨN_ĐOÁN",
  "candidates": ["K21.0", "K21.9"],
  "assertions": [],
  "position": [start, end]
}
```

```json
{
  "text": "Chlorpheniramine 0.4 MG/ML",
  "type": "THUỐC",
  "candidates": ["360047"],
  "assertions": ["isHistorical"],
  "position": [start, end]
}
```

`isHistorical` do pipeline suy luận từ cụm “có tiền sử sử dụng”; nó không nằm trong ICD hay RxNorm.

### Phân biệt các khái niệm

- **Code lookup**: đã biết mã/tên chuẩn và chỉ tra cứu, ví dụ “I10 là bệnh gì?”.
- **Entity linking**: cách viết tự nhiên được ánh xạ sang mã chuẩn, ví dụ “BN THA nhiều năm” → tăng huyết áp → `I10`.
- **Candidate generation**: tạo top-k mã tiềm năng trước khi rerank.

Metric Jaccard phạt candidate thừa. Không nên trả hàng loạt mã chỉ để “phòng hờ”.

---

## 3. Ví dụ ICD: `K21.0` và `K21.9`

Trong danh mục ICD-10 thường gặp:

```text
K00–K95  → Bệnh hệ tiêu hóa
K20–K31  → Bệnh thực quản, dạ dày và tá tràng
K21      → Trào ngược dạ dày–thực quản
K21.0    → Trào ngược có viêm thực quản
K21.9    → Trào ngược không có viêm thực quản
```

Điểm quyết định giữa `K21.0` và `K21.9` là có thông tin **viêm thực quản** hay không.

| Văn bản | Mã thường phù hợp | Giải thích |
|---|---:|---|
| “Trào ngược dạ dày–thực quản có viêm thực quản” | `K21.0` | Có GERD và viêm thực quản |
| “Viêm thực quản do trào ngược” | `K21.0` | Cùng khái niệm, khác thứ tự diễn đạt |
| “GERD kèm viêm thực quản” | `K21.0` | GERD là tên viết tắt |
| “Trào ngược dạ dày–thực quản” | `K21.9`* | Có chẩn đoán GERD nhưng không ghi viêm |
| “Ợ nóng sau khi ăn” | Có thể `R12` hoặc chỉ là triệu chứng | Không được tự suy luận thành GERD |
| “Viêm thực quản” | Chưa chắc `K21.0` | Chưa biết nguyên nhân có phải trào ngược không |

`*` Phải kiểm tra codebook chính thức của cuộc thi.

Không nên diễn giải máy móc từng ký tự của mã ICD. Ý nghĩa thuộc về toàn bộ category `K21` và các nhánh được định nghĩa trong category đó.

### ICD mapping và assertion là hai việc độc lập

```text
Bệnh nhân không bị trào ngược dạ dày thực quản có viêm thực quản.
```

Concept vẫn là `K21.0`, nhưng assertion là `isNegated`.

```json
{
  "text": "trào ngược dạ dày thực quản có viêm thực quản",
  "type": "CHẨN_ĐOÁN",
  "candidates": ["K21.0"],
  "assertions": ["isNegated"]
}
```

Tương tự, “tiền sử GERD” thường cho `K21.9` + `isHistorical`. Assertion không tự động thay đổi mã bệnh.

### Cảnh báo phiên bản ICD

Không trộn ICD-10 WHO, ICD-10-CM của Hoa Kỳ và danh mục Việt Nam. Trong ICD-10-CM hiện đại, `K21.0` có thể là mã cha, được chia thành `K21.00` (có viêm, không xuất huyết) và `K21.01` (có viêm, có xuất huyết). Cần kiểm tra ontology/codebook được ban tổ chức cung cấp trước khi xây pipeline.

---

## 4. Kiến trúc hybrid đề xuất

Không nên để model 5B đọc toàn bộ hồ sơ rồi tự sinh JSON. Nên chia thành các tầng có trách nhiệm rõ ràng:

```text
Văn bản gốc
→ tiền xử lý, giữ offset
→ entity proposal
→ phân loại type và hợp nhất span
→ assertion theo scope
→ ICD/RxNorm retrieval
→ reranking
→ chọn candidate
→ validator và JSON cuối
```

### Tầng 1: tiền xử lý

Giữ đồng thời:

- `raw_text`: dùng để xuất `text` và `position`.
- `normalized_text`: dùng để tìm kiếm/phân loại.

Có thể chuẩn hóa khoảng trắng, câu, viết tắt (`THA`, `ĐTĐ`, `ko`), đơn vị (`500mg` → `500 mg`) và section (`Tiền sử`, `Gia đình`, `Thuốc đang dùng`, ...). Cần duy trì ánh xạ chỉ số normalized → raw để không làm lệch offset.

### Tầng 2: entity proposal

Kết hợp ba nguồn:

1. **Regex**: bắt hàm lượng, đơn vị, số đo, xét nghiệm.
2. **Dictionary matching**: tên bệnh ICD, tên thuốc RxNorm, đồng nghĩa, viết tắt.
3. **Model span detector**: BIO tagging hoặc span classification để bắt cách diễn đạt mới.

Các span chồng lấn như `clonazepam`, `clonazepam 0.5 mg`, `0.5 mg` cần được hợp nhất theo quy tắc. Với thuốc, thường ưu tiên span đầy đủ gồm hoạt chất + hàm lượng. Hai lần xuất hiện ở hai vị trí khác nhau phải là hai entity riêng.

### Tầng 3: phân loại `type`

Các loại dự kiến:

```text
TRIỆU_CHỨNG
CHẨN_ĐOÁN
THUỐC
XÉT_NGHIỆM
THÔNG_TIN_BỆNH_NHÂN
```

Luật gợi ý:

- Tên hoạt chất + hàm lượng → `THUỐC`.
- Tên bệnh trong từ điển → `CHẨN_ĐOÁN`.
- Cụm mô tả biểu hiện → `TRIỆU_CHỨNG`.
- Tên chỉ số + đơn vị → `XÉT_NGHIỆM`.

Không nâng triệu chứng thành chẩn đoán nếu văn bản không xác nhận. Ví dụ “ợ nóng” không tự động thành GERD.

### Tầng 4: assertion và scope

Ba assertion chính:

- `isNegated`: phủ định, ví dụ “bệnh nhân không ho”.
- `isFamily`: thuộc người nhà, ví dụ “bố bệnh nhân bị tăng huyết áp”.
- `isHistorical`: tiền sử, ví dụ “có tiền sử GERD”.

Một entity có thể có nhiều assertion: “Mẹ bệnh nhân không bị hen” → `isFamily` + `isNegated`.

Không gán cue của cả câu cho mọi entity. Cần xác định phạm vi cục bộ và ngữ cảnh section.

---

## 5. Nhánh ICD trong pipeline

```text
mention bệnh
→ chuẩn hóa cách viết
→ sinh candidate ICD
→ đọc ngữ cảnh
→ rerank
→ chọn tập candidate cuối
```

Các đặc điểm cần xem xét:

- Tên bệnh chính.
- Vị trí tổn thương.
- Cấp tính/mạn tính.
- Biến chứng.
- Mức độ nặng.
- Nguyên nhân.
- Phiên bản ICD.

Ví dụ “đái tháo đường type 2 có biến chứng thận” phải dùng cụm “biến chứng thận” để đi vào nhánh mã chi tiết hơn, không chỉ trả mã chung type 2.

---

## 6. Nhánh RxNorm trong pipeline

Tách mention thuốc thành:

```text
ingredient
strength
dose form
route
release type
brand
```

Ví dụ:

```text
clonazepam 0.5 mg uống buổi tối
```

→ `ingredient=clonazepam`, `strength=0.5 mg`, `route=oral`, `schedule=buổi tối`.

`ingredient`, `strength` và `dose form` giúp tìm RxCUI; lịch dùng chủ yếu là ngữ cảnh. Hàm lượng và dạng thuốc là ràng buộc mạnh:

```text
0.5 mg ≠ 1.5 mg
tablet ≠ oral solution
immediate release ≠ extended release
```

Dense embedding có thể tìm thuốc tương tự nhưng không luôn tôn trọng con số; do đó cần parser và luật khớp cứng.

---

## 7. Candidate generation vs selection

Hai bước cần tách biệt:

- **Generation**: lấy nhóm nhỏ mã có khả năng đúng, ví dụ GERD → `K21.0`, `K21.9`.
- **Selection**: dùng ngữ cảnh để chọn tập cuối, ví dụ chỉ `K21.0`.

Nếu đáp án là `{K21.9}` mà trả `{K21.9, K21.0, K20.9}`, Jaccard chỉ còn `1/3`. Nên dùng ngưỡng:

```text
confidence cao   → top-1
confidence trung → có thể top-2
confidence thấp   → xử lý lại bằng rule/model hỗ trợ
```

---

## 8. Model 5B trên máy 4 GB VRAM

Ước lượng bộ nhớ trọng số:

| Kiểu | Bộ nhớ xấp xỉ |
|---|---:|
| FP32 | 20 GB |
| FP16/BF16 | 10 GB |
| INT8 | 5–7 GB |
| 4-bit | 2.5–4 GB |

Con số thực tế còn tăng do KV cache, activation, runtime và CUDA overhead. Model 5B 4-bit có thể chạy nhưng thường cần batch 1, context ngắn, CPU offload và RAM hệ thống ít nhất 16 GB (32 GB tốt hơn).

- Full fine-tuning: gần như không khả thi.
- LoRA thường: khó trên 4 GB.
- QLoRA: có thể thử nhưng chậm, cần gradient checkpointing, sequence ngắn và accumulation.

Kiến trúc phù hợp:

```text
regex + dictionary + encoder nhỏ
        ↓
phần lớn trường hợp thông thường
        ↓ (chỉ khi confidence thấp)
model 5B 4-bit
        ↓
ICD/RxNorm retrieval + rerank
        ↓
JSON validator
```

Model 5B nên hỗ trợ:

- Phân loại span mơ hồ.
- Xác định scope phủ định.
- Phân biệt triệu chứng/chẩn đoán.
- Rerank một số candidate ICD.
- Phân tích cách viết thuốc bất thường.
- Sinh dữ liệu synthetic offline.

Không nên giao cho model 5B việc quyết định offset, sinh JSON tự do, xử lý toàn bộ hồ sơ dài hoặc chạy mọi entity nếu model nhỏ/rule đã đủ chắc chắn.

---

## 9. Validator và output cuối

Validator phải kiểm tra:

```python
raw_text[start:end] == entity["text"]
```

Ngoài ra:

- `position` là `[start, end)`.
- `start < end` và không vượt độ dài văn bản.
- Không gộp nhầm các occurrence.
- `candidates` chỉ dùng với type thích hợp.
- Assertion chỉ thuộc tập giá trị hợp lệ.
- JSON đúng schema.
- Entity được sắp theo vị trí xuất hiện.

Model không được tự tạo text đã chuẩn hóa làm lệch span; hệ thống nên lấy text trực tiếp từ raw text dựa trên offset.

---

## 10. Ví dụ output tổng hợp

Input:

```text
Bố bệnh nhân không ho. Bệnh nhân có tiền sử GERD.
Hiện đang dùng clonazepam 0.5 mg uống buổi tối.
```

Output minh họa:

```json
[
  {
    "text": "ho",
    "type": "TRIỆU_CHỨNG",
    "assertions": ["isFamily", "isNegated"],
    "position": [18, 20]
  },
  {
    "text": "GERD",
    "type": "CHẨN_ĐOÁN",
    "assertions": ["isHistorical"],
    "candidates": ["K21.9"],
    "position": [52, 56]
  },
  {
    "text": "clonazepam 0.5 mg",
    "type": "THUỐC",
    "assertions": [],
    "candidates": ["197527"],
    "position": [79, 97]
  }
]
```

Các offset và RxCUI trong ví dụ chỉ minh họa; chương trình thật phải tính offset từ input và tra đúng ontology/codebook.

---

## 11. Việc cần làm tiếp theo

1. Lấy và kiểm tra schema/output format chính thức của Viettel AI Race.
2. Xác định chính xác bộ ICD/RxNorm và phiên bản ontology được chấm.
3. Tạo bộ dictionary bệnh, thuốc, viết tắt và đồng nghĩa tiếng Việt.
4. Viết offset-preserving normalizer.
5. Xây regex + dictionary baseline trước khi thêm model.
6. Tạo assertion engine theo câu và section.
7. Xây ICD/RxNorm candidate retrieval có luật khớp cứng.
8. Thêm encoder nhỏ để phát hiện span/type.
9. Chỉ gọi model 5B 4-bit cho ca khó hoặc confidence thấp.
10. Viết validator và đánh giá riêng từng thành phần: span, type, assertion, candidate và Jaccard.

## Kết luận ngắn

Bài toán nên được xem là bốn nhiệm vụ độc lập nhưng liên kết:

```text
1. Entity nằm ở đâu?
2. Entity thuộc loại gì?
3. Entity xuất hiện trong trạng thái nào?
4. Entity ánh xạ tới mã ICD/RxNorm nào?
```

Model 5B có thể hữu ích trên 4 GB VRAM nếu lượng tử hóa và chỉ dùng như chuyên gia hỗ trợ. Phần quyết định cuối cùng — đặc biệt là offset, schema, hàm lượng thuốc và candidate — nên do pipeline có cấu trúc và validator kiểm soát.
