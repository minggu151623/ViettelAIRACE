# i2b2/VA guideline extract — independent policy prior

Nguồn chính thức:

- [Concept Annotation Guideline](https://www.i2b2.org/NLP/Relations/assets/Concept%20Annotation%20Guideline.pdf)
- [Assertion Annotation Guideline](https://www.i2b2.org/NLP/Relations/assets/Assertion%20Annotation%20Guideline.pdf)

## Boundary rules có thể chuyển thành giả thuyết cho BTC

Concept guideline yêu cầu đánh dấu cụm danh từ/tính từ hoàn chỉnh, không đánh dấu thuật
ngữ chỉ làm modifier trong một noun phrase. Modifier cùng cụm được giữ lại, trừ modifier
mang nghĩa assertion. Có thể giữ tối đa một cụm giới từ sau concept nếu nó chỉ cơ quan/bộ
phận cơ thể hoặc vượt qua “PP test”; nếu PP chứa một concept khác thì tách thành hai
concept.

Liên từ/list chỉ nằm trong một span khi các phần trong list dùng chung modifiers; các mục
độc lập phải tách riêng. Hai cách gọi của cùng khái niệm trong một noun phrase (ví dụ tên
generic và brand của thuốc) được giữ cùng nhau. Mỗi occurrence được annotate riêng.

Các header chỉ để định dạng, không gắn với một người, không phải concept. Concept phải
liên quan đến bệnh nhân hoặc người khác trong ghi chú; không lấy mọi từ y khoa xuất hiện
trong văn bản.

## Assertion rules

Assertion guideline gốc của i2b2 gán một trong sáu lớp loại trừ nhau cho medical problem:
Present, Absent, Possible, Conditional, Hypothetical, Not associated with Patient.
“Possible” được ưu tiên hơn “Absent”, nên “probably not” vẫn là Possible. Present là
mặc định. Assertion của i2b2 là time-independent; đây là khác biệt với schema BTC có
list assertion và `isHistorical`.

| i2b2 | Ánh xạ giả thuyết BTC |
|---|---|
| Absent | `isNegated` |
| Not associated with Patient | `isFamily` hoặc experiencer khác |
| Present | assertion list rỗng |
| historical wording | chỉ là tín hiệu `isHistorical` theo policy BTC riêng |

## Giới hạn bằng chứng

Đây là guideline của một nhiệm vụ i2b2/VA khác, không phải annotation guideline của
Viettel. BTC đã công khai rằng assertion là multilabel và có thể gắn historical cho thuốc,
nên không được sao chép nhãn i2b2 một cách máy móc. Giá trị hiện tại của nguồn là cung cấp
quy tắc biên span và scope có cấu trúc để thiết kế/kiểm thử giả thuyết độc lập.
