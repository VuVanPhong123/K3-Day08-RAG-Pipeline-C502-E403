# Báo cáo nhóm — University Admission RAG Assistant

## 1. Thông tin nhóm

| Thành viên | MSSV | Vai trò chính |
|---|---|---|
| **Vũ Văn Phong** | **2A202601647** | **Nhóm trưởng, RAG Architect và Integration Lead** |
| Đoàn Nhật Nam | 2A202601123 | Data Engineering & Scraping Developer |
| Hà Duy Anh | 2A202601511 | Data Standardization & Vector DB Developer |
| Nguyễn Quang Vinh | 2A202601517 | Dense & Sparse Retrieval Developer |
| Hoàng Lê Minh | 2A202601653 | Reranking & Fallback Developer |
| Phạm Sỹ Đức | 2A202601601 | Generation & Frontend Developer |

## 2. Đề tài

**University Admission RAG Assistant** là chatbot hỗ trợ tra cứu điểm chuẩn, phương thức xét tuyển, chỉ tiêu, điều kiện IELTS/SAT, học phí, học bổng, hồ sơ và mốc thời gian tuyển sinh từ nguồn chính thức.

Phạm vi dữ liệu hiện tại gồm HUST, VinUniversity, RMIT Việt Nam và HCMUS. Mỗi câu trả lời factual phải gắn citation, năm tuyển sinh và nguồn evidence.

## 3. Đối chiếu yêu cầu bài lab

| Yêu cầu | Kết quả |
|---|---|
| Tối thiểu 3 PDF/DOCX chính sách | Đã có tài liệu chính thức và manifest nguồn trong `data/landing/legal/` |
| Tối thiểu 5 bài viết/thông báo | Đã crawl nhiều nguồn chính thức trong `data/landing/news/` |
| Chuyển dữ liệu sang Markdown | Đã chuẩn hóa tại `data/standardized/` |
| Chunking và ChromaDB | Recursive chunking 800/100, vector 1024 chiều, cosine distance |
| Semantic search | Có Task 5 và cùng embedding backend với index |
| BM25/TF-IDF | Có Task 6, hỗ trợ Unicode và token số/mã ngành |
| Reranking | Có RRF, MMR và optional Jina |
| PageIndex vectorless fallback | Có SDK integration và local structural fallback |
| Retrieval pipeline | Có Semantic + BM25 + metadata-targeted search + RRF + fallback |
| Generation có citation | Có Gemini/OpenAI/local extractive, citation validation và quality gate |
| Giao diện chat | Có React + FastAPI và Streamlit dự phòng |
| Conversation memory | Có history và contextualization cho follow-up |
| Hiển thị source documents | Có source expander, URL, năm, score, backend và evidence |
| Golden dataset tối thiểu 15 câu | Có 18 câu hỏi |
| 4 evaluation metrics | Faithfulness, Answer Relevance, Context Recall, Context Precision |
| A/B testing | Hybrid RAG so với Dense-only |
| Báo cáo worst performers | Có Bottom 3 và recommendations trong `results.md` |

## 4. Phân công chi tiết

### Vũ Văn Phong — Nhóm trưởng

- Thiết kế kiến trúc tổng thể.
- Tích hợp Task 9 hybrid retrieval.
- Kết nối FastAPI với Task 10.
- Review code giữa các module.
- Điều phối dữ liệu, evaluation và demo.
- Tổng hợp README, báo cáo nhóm và kịch bản trình bày.

### Đoàn Nhật Nam — Data Engineering & Scraping

- Thu thập PDF chính thức và tạo provenance manifest.
- Crawl nguồn tuyển sinh.
- Phát hiện trang listing/document pointer.
- Follow nguồn con có kiểm soát.
- Kiểm tra spam, menu/footer và chất lượng raw data.

### Hà Duy Anh — Standardization & Vector DB

- Chuyển dữ liệu sang Markdown UTF-8.
- Chuẩn hóa metadata và curated tables.
- Chunking 800/100.
- ChromaDB, fingerprint và rebuild index.
- Kiểm tra consistency giữa corpus và embedding backend.

### Nguyễn Quang Vinh — Dense & Sparse Retrieval

- Semantic search.
- BM25 và TF-IDF.
- Tokenization cho tiếng Việt, năm, mã ngành và chứng chỉ.
- Retrieval smoke tests.
- Hỗ trợ benchmark Hybrid và Dense-only.

### Hoàng Lê Minh — Reranking & Fallback

- RRF `k=60` và deduplication.
- MMR/optional Jina reranking.
- PageIndex upload/query registry.
- Retry và local structural fallback.
- Kiểm tra fallback theo cosine gốc.

### Phạm Sỹ Đức — Generation & Frontend

- Generation có citation.
- Context reordering và quality gate.
- Conversation memory.
- Streamlit UI.
- React frontend và source/evidence display.

## 5. Kiến trúc triển khai

```text
User
  -> React FE hoặc Streamlit
  -> FastAPI đối với React
  -> Task 10 Generation
       -> conversation memory
       -> quality gate
       -> citation validation
  -> Task 9 Retrieval
       -> Semantic / ChromaDB
       -> BM25 / TF-IDF
       -> Metadata-targeted search
       -> RRF / optional Jina
       -> PageIndex hoặc local structural fallback
  -> Answer + citations + sources
```

## 6. Dữ liệu

Dữ liệu được chia thành:

- `data/landing/legal/`: PDF gốc và source manifest.
- `data/landing/news/`: JSON crawl kèm metadata.
- `data/standardized/`: Markdown dùng để chunk/index.
- `data/curated/`: bảng dữ liệu đã xác minh, phục vụ câu hỏi số liệu chính xác.
- `data/data_quality_report.json`: phân loại chất lượng từng nguồn.

Các trang listing/document pointer không được dùng làm primary evidence khi có tài liệu chi tiết hơn.

## 7. Kết quả evaluation

Lần chạy gần nhất:

- Framework: **Local proxy evaluation — not official RAGAS scores**.
- Số câu hỏi: **18**.
- Corpus fingerprint: `e6f6e9a6862c8bd1dc3ccf97a9c9d29d`.

| Metric | Hybrid | Dense-only | Chênh lệch |
|---|---:|---:|---:|
| Faithfulness | 0.6098 | 0.6355 | -0.0257 |
| Answer Relevance | 0.2005 | 0.1955 | +0.0050 |
| Context Recall | 0.9444 | 0.6737 | +0.2707 |
| Context Precision | 0.9444 | 0.9444 | 0.0000 |
| **Average** | **0.6748** | **0.6123** | **+0.0625** |

### Nhận xét

- Hybrid retrieval cải thiện Context Recall rõ rệt.
- Answer Relevance chỉ tăng nhẹ vì local extractive generation còn hạn chế.
- Faithfulness của Hybrid thấp hơn nhẹ; lấy nhiều evidence hơn có thể làm câu trả lời dài và phân tán.
- Nên bật BGE-M3 thật và chạy RAGAS bằng Gemini/OpenAI judge khi quota cho phép.

## 8. Hạn chế

- Mặc định offline dùng `local_hashing_1024`; BGE-M3 chỉ chạy khi bật tải model.
- Evaluation hiện là proxy local, không phải điểm RAGAS chính thức.
- Một số PDF scan có ít text extractable.
- HCMUS cutoff chưa index raw OCR chưa xác minh.
- RMIT important-dates hub chưa có mốc ngày chi tiết trong phần text crawl được.
- Jina là tùy chọn; cấu hình mặc định hiện dùng RRF.

## 9. Hướng dẫn chạy

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -X utf8 -m src.task1_collect_legal_docs
.\.venv\Scripts\python.exe -X utf8 -m src.task2_crawl_news
.\.venv\Scripts\python.exe -X utf8 -m src.task3_convert_markdown
.\.venv\Scripts\python.exe -X utf8 -m src.task4_chunking_indexing
.\.venv\Scripts\python.exe -X utf8 -m uvicorn api:app --reload --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Streamlit dự phòng:

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

## 10. Kiểm thử

```powershell
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_individual.py -v
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/ -v
cd frontend
npm run build
```

Báo cáo này mô tả trạng thái code và kết quả hiện có trong repository. Không xem local proxy là RAGAS chính thức và không khẳng định backend tùy chọn đã chạy nếu demo thực tế đang dùng fallback.
