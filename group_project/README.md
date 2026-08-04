# Group Project - University Admission RAG Assistant

## Mục Tiêu

Xây dựng chatbot RAG tra cứu tuyển sinh đại học: điểm chuẩn, phương thức xét tuyển, điều kiện IELTS/SAT, học phí, học bổng, chỉ tiêu, hồ sơ và timeline từ nguồn chính thức.

## Kiến Trúc

```text
Streamlit
  -> Conversation memory
  -> Task 9 retrieval pipeline
       -> Semantic search / ChromaDB
       -> BM25 + TF-IDF
       -> RRF
       -> PageIndex hoặc local structural fallback
  -> Task 10 Gemini/OpenAI/local generation
  -> Answer with citations + source evidence
```

## Phân Công 6 Thành Viên

| Thành viên | MSSV | Vai trò | Công việc |
|---|---|---|---|
| Vũ Văn Phong | 2A202601647 | Team Leader & RAG Architect | Kiến trúc, Task 9, tích hợp, code review, demo |
| `[TÊN THÀNH VIÊN 2]` | `[MSSV 2]` | Data Engineering & Scraping Developer | Task 1-3 |
| `[TÊN THÀNH VIÊN 3]` | `[MSSV 3]` | Vector Database & Dense Search Developer | Task 4-5 |
| `[TÊN THÀNH VIÊN 4]` | `[MSSV 4]` | Sparse Retrieval & Fallback Developer | Task 6-8 |
| `[TÊN THÀNH VIÊN 5]` | `[MSSV 5]` | Frontend & Generation Developer | Task 10 và Streamlit |
| `[TÊN THÀNH VIÊN 6]` | `[MSSV 6]` | Evaluation & QA Developer | Golden dataset, RAGAS, A/B, báo cáo |

## Hướng Dẫn Chạy

```powershell
.\.venv\Scripts\python.exe -X utf8 -m src.task1_collect_legal_docs
.\.venv\Scripts\python.exe -X utf8 -m src.task2_crawl_news
.\.venv\Scripts\python.exe -X utf8 -m src.task3_convert_markdown
.\.venv\Scripts\python.exe -X utf8 -m src.task4_chunking_indexing
.\.venv\Scripts\streamlit.exe run app.py
```

## Evaluation

```powershell
.\.venv\Scripts\python.exe -X utf8 -m group_project.evaluation.eval_pipeline --limit 5
```

Evaluation hiện hỗ trợ:

- Config A: Semantic + BM25 + RRF + fallback.
- Config B: Dense-only.
- Local proxy metrics khi không có judge key.
- RAGAS thật khi có Gemini/OpenAI judge.

## Demo Checklist

- Hỏi điều kiện IELTS vào HUST.
- Hỏi học phí RMIT hoặc VinUni.
- Hỏi học bổng VinUni.
- Hỏi điểm chuẩn Công nghệ thông tin.
- Hỏi follow-up: "Còn SAT thì sao?"
- Mở source expander và chỉ ra citation, URL, năm tuyển sinh, backend.
- Chạy evaluation A/B và mở `group_project/evaluation/results.md`.

## Lưu Ý

Không commit `.env`, API key, cache hoặc dữ liệu tạm. Dữ liệu tuyển sinh thay đổi theo năm nên câu trả lời phải luôn đi kèm citation và năm nguồn.
