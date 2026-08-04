# Group Project — University Admission RAG Assistant

## 1. Mục tiêu

Xây dựng chatbot RAG hỗ trợ học sinh và phụ huynh tra cứu thông tin tuyển sinh đại học từ nguồn chính thức, gồm điểm chuẩn, phương thức xét tuyển, điều kiện IELTS/SAT, chỉ tiêu, học phí, học bổng, hồ sơ và mốc thời gian.

Sản phẩm đáp ứng hai deliverable chính của bài lab:

1. Chatbot có giao diện, conversation memory, câu trả lời có citation và hiển thị tài liệu nguồn.
2. Evaluation pipeline có golden dataset từ 15 câu trở lên, bốn metric, so sánh A/B, phân tích câu kém nhất và đề xuất cải tiến.

## 2. Thành viên và phân công

| Thành viên | MSSV | Vai trò | Phạm vi phụ trách | Trạng thái |
|---|---|---|---|---|
| **Vũ Văn Phong** | **2A202601647** | **Team Leader & RAG Architect** | Thiết kế kiến trúc; Task 9 hybrid retrieval; tích hợp FastAPI; code review; điều phối A/B evaluation; tổng hợp báo cáo và demo | Hoàn thành |
| Đoàn Nhật Nam | 2A202601123 | Data Engineering & Scraping Developer | Task 1–2; thu thập PDF và crawl nguồn chính thức; provenance; phát hiện trang listing/document pointer; kiểm tra data hygiene | Hoàn thành |
| Hà Duy Anh | 2A202601511 | Data Standardization & Vector DB Developer | Task 3–4; chuẩn hóa Markdown; chunking; metadata; ChromaDB; fingerprint và rebuild index; kiểm tra evidence của golden dataset | Hoàn thành |
| Nguyễn Quang Vinh | 2A202601517 | Dense & Sparse Retrieval Developer | Task 5–6; semantic search; BM25/TF-IDF; retrieval smoke test; hỗ trợ benchmark hybrid và dense-only | Hoàn thành |
| Hoàng Lê Minh | 2A202601653 | Reranking & Fallback Developer | Task 7–8; RRF/Jina reranking; PageIndex API; local structural fallback; registry/retry và fallback test | Hoàn thành |
| Phạm Sỹ Đức | 2A202601601 | Generation & Frontend Developer | Task 10; generation có citation; quality gate; conversation memory; Streamlit và React UI; hiển thị source/evidence | Hoàn thành |

Phân công được chia theo sáu khối độc lập của pipeline. Nhóm trưởng đảm nhiệm tích hợp và kiểm soát chất lượng thay vì gom thêm toàn bộ phần triển khai của một thành viên khác.

## 3. Kiến trúc hệ thống

```text
                       ┌───────────────────────┐
                       │ React FE / Streamlit  │
                       └───────────┬───────────┘
                                   │
                         React dùng FastAPI
                                   │
                                   v
                       ┌───────────────────────┐
                       │ Task 10 Generation    │
                       │ citation + memory     │
                       │ quality gate          │
                       └───────────┬───────────┘
                                   │
                                   v
                       ┌───────────────────────┐
                       │ Task 9 Hybrid RAG     │
                       └───────────┬───────────┘
                                   │
           ┌───────────────────────┼────────────────────────┐
           │                       │                        │
           v                       v                        v
  BGE-M3/Local Hash +       BM25 / TF-IDF         Metadata-targeted search
       ChromaDB
           └───────────────────────┬────────────────────────┘
                                   v
                          RRF / optional Jina
                                   │
                         cosine quality threshold
                                   │
                ┌──────────────────┴──────────────────┐
                │                                     │
                v                                     v
          Hybrid results                  PageIndex / local structural
                └──────────────────┬──────────────────┘
                                   v
                       Answer + citations + sources
```

## 4. Dữ liệu và provenance

Corpus sử dụng nguồn chính thức của:

- Đại học Bách khoa Hà Nội: thông tin tuyển sinh 2026, quy chế/XTTN 2026, chỉ tiêu và một phần điểm chuẩn 2025 có evidence text.
- VinUniversity: học phí 2026–2027, học bổng và hỗ trợ tài chính.
- RMIT Việt Nam: học phí 2026, Bachelor of Computer Science, quy trình đăng ký và international student guide.
- Trường Đại học Khoa học tự nhiên, ĐHQG-HCM: thông tin tuyển sinh 2025, phụ lục chỉ tiêu/phương thức và các thông báo phương thức chi tiết.

Các nguồn được phân loại thành `detail_page`, `table_page`, `document_pointer`, `listing_page` và `mixed_page`. Trang listing hoặc document pointer được giữ để truy vết nhưng không dùng làm primary evidence khi đã có nguồn chi tiết hơn.

Dữ liệu cấu trúc đã xác minh nằm trong `data/curated/`, gồm điểm chuẩn HUST có evidence rõ, chỉ tiêu IT1 HUST 2026, bảng học phí RMIT giữ quan hệ giữa tên chương trình và mức phí, cùng bảng học bổng VinUni.

## 5. Luồng xử lý Task 1–10

| Task | Kết quả triển khai |
|---|---|
| Task 1 | Tải tài liệu PDF chính thức, kiểm tra content type, kích thước và lưu manifest nguồn |
| Task 2 | Crawl trang tuyển sinh, làm sạch menu/footer/spam, phân loại page type và follow nguồn con có kiểm soát |
| Task 3 | Chuyển PDF/JSON sang Markdown có metadata và giữ UTF-8 tiếng Việt |
| Task 4 | Recursive chunking `800/100`, embedding 1024 chiều, ChromaDB cosine và rebuild theo fingerprint |
| Task 5 | Semantic search trả content, score và metadata; dùng cùng embedding backend với index |
| Task 6 | BM25 và TF-IDF Unicode, giữ năm, mã ngành, IELTS/SAT và số điểm |
| Task 7 | RRF `k=60`, deduplicate chunk và hỗ trợ optional Jina/MMR fallback |
| Task 8 | PageIndex SDK khi có key; local structural fallback khi API không khả dụng |
| Task 9 | Semantic + BM25 chạy song song, metadata-targeted search, RRF và fallback dựa trên cosine gốc |
| Task 10 | Reorder context, Gemini/OpenAI/local extractive generation, citation validation, memory và quality gate |

## 6. Giao diện và API

### React + FastAPI

```powershell
.\.venv\Scripts\python.exe -X utf8 -m uvicorn api:app --reload --port 8000
cd frontend
npm install
npm run dev
```

React sử dụng `VITE_API_URL`, không chứa API key. FastAPI cung cấp:

- `GET /api/health`
- `GET /api/suggestions`
- `POST /api/chat`

### Streamlit dự phòng

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

Hai giao diện đều hỗ trợ câu hỏi gợi ý, `top_k`, history, source expander, URL, score, năm tuyển sinh và retrieval backend.

## 7. Evaluation

Golden dataset hiện có **18 câu hỏi**, vượt yêu cầu tối thiểu 15 câu. Hai cấu hình được so sánh:

- **Config A:** Semantic + BM25 + RRF + fallback.
- **Config B:** Dense-only.

Kết quả gần nhất dùng **local deterministic proxy**, không phải RAGAS chính thức:

| Metric | Config A | Config B | Delta |
|---|---:|---:|---:|
| Faithfulness | 0.6098 | 0.6355 | -0.0257 |
| Answer Relevance | 0.2005 | 0.1955 | +0.0050 |
| Context Recall | 0.9444 | 0.6737 | +0.2707 |
| Context Precision | 0.9444 | 0.9444 | 0.0000 |
| **Average** | **0.6748** | **0.6123** | **+0.0625** |

Hybrid retrieval cải thiện rõ nhất ở Context Recall. Faithfulness của Config A thấp hơn nhẹ, cho thấy lấy được nhiều evidence hơn chưa đồng nghĩa câu trả lời extractive luôn cô đọng và chính xác hơn. Kết quả chi tiết và bottom-3 nằm tại `group_project/evaluation/results.md`.

Chạy evaluation:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m group_project.evaluation.eval_pipeline --limit 5
.\.venv\Scripts\python.exe -X utf8 -m group_project.evaluation.eval_pipeline --resume
```

Chạy RAGAS thật khi có Gemini/OpenAI judge:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m group_project.evaluation.eval_pipeline --ragas --limit 5
```

## 8. Kiểm thử

```powershell
.\.venv\Scripts\python.exe -X utf8 -m compileall -q src group_project app.py api.py
.\.venv\Scripts\python.exe -m json.tool group_project/evaluation/golden_dataset.json
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_individual.py -v
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/ -v
.\.venv\Scripts\python.exe -m pip check
cd frontend
npm install
npm run build
git diff --check
```

## 9. Demo checklist

1. Kiểm tra `/api/health` và actual embedding backend.
2. Hỏi điều kiện IELTS vào HUST năm 2026.
3. Hỏi chứng chỉ SAT/ACT/A-Level/AP/IB tại HUST.
4. Hỏi chỉ tiêu ngành IT1 HUST năm 2026.
5. Hỏi học phí Computer Science tại RMIT năm 2026.
6. Hỏi các mức học bổng VinUni.
7. Hỏi follow-up: `Còn SAT thì sao?`.
8. Mở source expander để chỉ citation, URL, năm và evidence.
9. Hỏi câu ngoài phạm vi để trình bày quality gate.
10. Mở `group_project/evaluation/results.md` và so sánh A/B.

## 10. Hạn chế đã biết

- Khi `ADMISSION_RAG_DOWNLOAD_MODELS=0`, embedding thực tế là `local_hashing_1024`, không phải BGE-M3.
- Kết quả hiện tại là local proxy; chưa được trình bày như điểm RAGAS chính thức.
- VinUni admission scheme và HCMUS cutoff page có ít text extractable; không index raw OCR chưa xác minh.
- RMIT important-dates hub chưa cung cấp các mốc ngày chi tiết trong text đã crawl.
- Jina là backend tùy chọn; cấu hình mặc định của pipeline hiện dùng RRF.
- Dữ liệu tuyển sinh thay đổi theo từng năm, nên câu trả lời phải luôn kèm citation và năm nguồn.

## 11. Repository hygiene

Không commit `.env`, API key, cache, file tạm hoặc dữ liệu chưa xác minh. Tất cả source, JSON và Markdown dùng UTF-8 và giữ đầy đủ dấu tiếng Việt.
