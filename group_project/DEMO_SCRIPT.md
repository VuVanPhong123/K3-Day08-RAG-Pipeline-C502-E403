# Demo Script — University Admission RAG Assistant

## 1. Vấn đề

Học sinh và phụ huynh phải đọc nhiều trang tuyển sinh khác nhau để so sánh điểm chuẩn, học phí, học bổng và điều kiện xét tuyển. Thông tin thay đổi theo từng năm nên chatbot phải trả lời dựa trên nguồn chính thức, chỉ rõ năm và citation.

## 2. Thành viên trình bày

| Thành viên | MSSV | Nội dung trình bày |
|---|---|---|
| **Vũ Văn Phong** | **2A202601647** | Mở đầu, kiến trúc tổng thể, Task 9, tích hợp hệ thống, kết luận |
| Đoàn Nhật Nam | 2A202601123 | Nguồn dữ liệu, PDF, crawler, provenance và data hygiene |
| Hà Duy Anh | 2A202601511 | Markdown, chunking, metadata, ChromaDB và index fingerprint |
| Nguyễn Quang Vinh | 2A202601517 | Semantic search, BM25/TF-IDF và sự khác nhau giữa dense/sparse retrieval |
| Hoàng Lê Minh | 2A202601653 | RRF, Jina tùy chọn, PageIndex và local structural fallback |
| Phạm Sỹ Đức | 2A202601601 | Generation có citation, quality gate, memory, React và Streamlit |

## 3. Kiến trúc

```text
React FE / Streamlit
        |
        v
FastAPI API (React only)
        |
        v
Task 10 Generation
        |
        v
Task 9 Hybrid Retrieval
  -> Semantic / ChromaDB
  -> BM25 / TF-IDF
  -> Metadata-targeted search
  -> RRF / optional Jina
  -> Cosine quality threshold
  -> PageIndex API hoặc local structural fallback
        |
        v
Answer + citations + source evidence
```

Streamlit (`app.py`) là giao diện dự phòng nếu máy demo không chạy được frontend.

## 4. Dữ liệu

Nguồn chính thức: HUST, VinUniversity, RMIT Việt Nam và HCMUS.

Khi trình bày, mở:

- `data/landing/legal/sources.json`
- `data/data_quality_report.json`
- `data/curated/`
- Một số file trong `data/standardized/`

Giải thích:

- `detail_page` và `table_page` có thể là primary evidence.
- `listing_page` và `document_pointer` chủ yếu dùng cho provenance.
- Curated data chỉ giữ thông tin đã có evidence text rõ.

## 5. Chạy ứng dụng

Terminal 1:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m uvicorn api:app --reload --port 8000
```

Terminal 2:

```powershell
cd frontend
npm run dev
```

Mở:

```text
http://127.0.0.1:5173
```

Chỉ ra:

- Badge API/index.
- Embedding backend thực tế.
- Selector `top_k`.
- Câu hỏi gợi ý.
- Tin nhắn user/assistant.
- Accordion nguồn tham khảo.

## 6. Kịch bản câu hỏi

### Câu 1 — HUST IELTS

```text
Điều kiện IELTS vào HUST năm 2026 là gì?
```

Chỉ ra citation, năm 2026 và evidence.

### Câu 2 — Conversation memory

```text
Còn SAT thì sao?
```

Giải thích câu hỏi được contextualize với HUST từ lượt trước và history không chứa lặp câu hiện tại.

### Câu 3 — Chỉ tiêu chính xác

```text
Chỉ tiêu ngành CNTT: Khoa học Máy tính mã IT1 của HUST năm 2026 là bao nhiêu?
```

Chỉ ra curated evidence IT1 = 300 và phân biệt với TROY-IT.

### Câu 4 — RMIT

```text
Học phí Computer Science tại RMIT năm 2026 là bao nhiêu?
```

Giải thích bảng curated giữ quan hệ giữa tên chương trình và mức phí.

### Câu 5 — VinUni

```text
Các mức học bổng merit-based của VinUni dao động từ bao nhiêu đến bao nhiêu?
```

Chỉ ra source học bổng chính thức và mức 50%–100%.

### Câu 6 — Quality gate

```text
Giá Bitcoin ngày mai là bao nhiêu?
```

Hệ thống phải từ chối vì ngoài phạm vi thay vì lấy một chunk tuyển sinh bất kỳ.

## 7. Retrieval

Giải thích:

- Semantic search mạnh với diễn đạt tự nhiên và từ đồng nghĩa.
- BM25/TF-IDF mạnh với mã ngành, năm, số điểm, IELTS/SAT.
- Metadata-targeted search hỗ trợ truy vấn nêu rõ tên trường.
- RRF gộp thứ hạng mà không cộng trực tiếp cosine và BM25.
- Fallback phải dựa trên cosine gốc, không dùng điểm RRF.

## 8. PageIndex và fallback

Trình bày hai backend:

1. PageIndex SDK khi có API key và tài liệu xử lý thành công.
2. Local structural fallback dựa trên heading/section khi thiếu key hoặc API lỗi.

Không tuyên bố PageIndex/Jina đang chạy nếu demo thực tế dùng fallback/RRF.

## 9. Evaluation

Chạy:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m group_project.evaluation.eval_pipeline --limit 5
```

Mở `group_project/evaluation/results.md`.

Kết quả gần nhất:

| Metric | Hybrid | Dense-only |
|---|---:|---:|
| Faithfulness | 0.6098 | 0.6355 |
| Answer Relevance | 0.2005 | 0.1955 |
| Context Recall | 0.9444 | 0.6737 |
| Context Precision | 0.9444 | 0.9444 |
| Average | 0.6748 | 0.6123 |

Nêu rõ đây là **local proxy evaluation**, không phải RAGAS chính thức. Hybrid cải thiện Context Recall rõ nhất nhưng vẫn cần BGE-M3 thật và LLM judge để đánh giá tốt hơn.

## 10. Streamlit dự phòng

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

## 11. Kết luận

Nhấn mạnh ba điểm:

1. Pipeline end-to-end từ dữ liệu thật tới câu trả lời có citation.
2. Hybrid retrieval tăng khả năng lấy đủ evidence so với dense-only.
3. Hệ thống công khai fallback và giới hạn dữ liệu, không giả vờ đã xác minh khi evidence không đủ.
