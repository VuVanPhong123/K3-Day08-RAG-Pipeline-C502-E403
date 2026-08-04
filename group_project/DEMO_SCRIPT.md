# Demo Script - University Admission RAG Assistant

## 1. Vấn Đề

Học sinh và phụ huynh phải đọc nhiều trang tuyển sinh khác nhau để so sánh điểm chuẩn, học phí, học bổng và điều kiện xét tuyển. Thông tin lại thay đổi theo từng năm nên chatbot phải trả lời có nguồn.

## 2. Kiến Trúc

Trình bày luồng: Streamlit -> memory -> hybrid retrieval -> RRF -> fallback -> generation có citation.

## 3. Dữ Liệu

Nguồn chính thức: HUST, VinUniversity, RMIT Việt Nam, HCMUS. Mở `data/landing/legal/sources.json` và vài file Markdown trong `data/standardized/`.

## 4. Retrieval

Demo semantic search và BM25. Giải thích BM25 mạnh với năm, mã ngành, điểm số; semantic search mạnh với diễn đạt tự nhiên.

## 5. RRF Và Fallback

Giải thích RRF gộp thứ hạng, không dùng điểm RRF để quyết định fallback. Fallback dựa trên cosine score gốc và dùng PageIndex/local structural retrieval.

## 6. Generation Có Citation

Hỏi:

```text
Học phí chương trình đại học tại RMIT Việt Nam là bao nhiêu?
```

Chỉ ra citation, nguồn, năm và evidence trong expander.

## 7. Conversation Memory

Hỏi:

```text
Điều kiện xét tuyển bằng IELTS vào Đại học Bách khoa Hà Nội là gì?
Còn SAT thì sao?
```

Giải thích câu thứ hai được gửi kèm lịch sử gần nhất.

## 8. Evaluation

Chạy:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m group_project.evaluation.eval_pipeline --limit 5
```

Mở `group_project/evaluation/results.md`, trình bày Config A và Config B.

## 9. Phân Vai Trình Bày

- Vũ Văn Phong: kiến trúc, Task 9, tích hợp, demo tổng.
- `[TÊN THÀNH VIÊN 2]`: dữ liệu và convert.
- `[TÊN THÀNH VIÊN 3]`: ChromaDB và semantic search.
- `[TÊN THÀNH VIÊN 4]`: BM25, TF-IDF, RRF, PageIndex fallback.
- `[TÊN THÀNH VIÊN 5]`: Streamlit và generation.
- `[TÊN THÀNH VIÊN 6]`: golden dataset, evaluation, QA.
