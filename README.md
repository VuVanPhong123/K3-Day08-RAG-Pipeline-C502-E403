# University Admission RAG Assistant

Trợ lý AI tra cứu điểm chuẩn và đề án tuyển sinh đại học. Hệ thống hỗ trợ học sinh THPT và phụ huynh tra cứu, so sánh và tổng hợp thông tin tuyển sinh từ nguồn chính thức như đề án tuyển sinh, thông báo điểm chuẩn, học phí, học bổng, chỉ tiêu và phương thức xét tuyển.

## Phạm Vi Dữ Liệu

Corpus hiện dùng các nguồn chính thức từ:

- Đại học Bách khoa Hà Nội: thông tin tuyển sinh, quy chế tuyển sinh, điểm chuẩn.
- VinUniversity: đề án tuyển sinh, học phí, học bổng.
- RMIT Việt Nam: học phí, hướng dẫn tuyển sinh/sinh viên quốc tế.
- Trường Đại học Khoa học tự nhiên, ĐHQG-HCM: đề án tuyển sinh, chỉ tiêu, phương thức xét tuyển.

Tuyển sinh thay đổi theo từng năm. Khi demo hoặc sử dụng thực tế, luôn kiểm tra lại URL nguồn và năm tuyển sinh trong citation.

## Kiến Trúc

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
  -> BM25
  -> RRF / Jina
  -> PageIndex API or local fallback
```

Evaluation flow:

```text
Golden Dataset
  -> Config A: Semantic + BM25 + RRF + fallback
  -> Config B: Dense-only
  -> RAG pipeline
  -> RAGAS nếu có judge key hoặc local proxy metrics
  -> group_project/evaluation/results.md
```

## Cài Đặt

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:PYTHONUTF8="1"
$env:PYTHONIOENCODING="utf-8"
```

Linux/macOS:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8
```

Nếu Crawl4AI cần Chromium:

```bash
playwright install chromium
```

## Biến Môi Trường

Tạo `.env` từ `.env.example`. Không commit `.env`.

```env
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.5-flash-lite
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
PAGEINDEX_API_KEY=
FRONTEND_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
JINA_API_KEY=
ADMISSION_RAG_DOWNLOAD_MODELS=0
```

Provider priority: Gemini, OpenAI, local extractive fallback.

Gemini mặc định dùng `gemini-3.5-flash-lite`. Với Gemini 3.5/3.6 và các model mới hơn, code không truyền `temperature`, `top_p` hoặc `top_k` để tránh sampling parameters đã deprecated; vẫn truyền `system_instruction`, `max_output_tokens` và HTTP timeout.

## Chạy Pipeline

```powershell
.\.venv\Scripts\python.exe -X utf8 -m src.task1_collect_legal_docs
.\.venv\Scripts\python.exe -X utf8 -m src.task2_crawl_news
.\.venv\Scripts\python.exe -X utf8 -m src.task3_convert_markdown
.\.venv\Scripts\python.exe -X utf8 -m src.task4_chunking_indexing
.\.venv\Scripts\python.exe -X utf8 -m src.task5_semantic_search
.\.venv\Scripts\python.exe -X utf8 -m src.task6_lexical_search
.\.venv\Scripts\python.exe -X utf8 -m src.task7_reranking
.\.venv\Scripts\python.exe -X utf8 -m src.task8_pageindex_vectorless
.\.venv\Scripts\python.exe -X utf8 -m src.task9_retrieval_pipeline
.\.venv\Scripts\python.exe -X utf8 -m src.task10_generation
```

## Chạy Backend API

```powershell
.\.venv\Scripts\python.exe -X utf8 -m uvicorn api:app --reload --port 8000
```

Các endpoint:

- `GET /api/health`: trạng thái index, chunk count, generator, PageIndex backend và embedding backend.
- `GET /api/suggestions`: 5 câu hỏi gợi ý.
- `POST /api/chat`: gọi `generate_with_citation()` và trả answer/sources an toàn cho React.

## Chạy React

```powershell
cd frontend
npm install
npm run dev
```

Frontend chỉ dùng `VITE_API_URL`, không chứa secret và không gọi trực tiếp Python module.

## Chạy Streamlit

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

Streamlit được giữ làm giao diện dự phòng. Cả React và Streamlit đều có chat history, câu hỏi gợi ý, `top_k`, source expander, score, URL, năm tuyển sinh và backend retrieval.

## Evaluation

```powershell
.\.venv\Scripts\python.exe -X utf8 -m group_project.evaluation.eval_pipeline --limit 5
.\.venv\Scripts\python.exe -X utf8 -m group_project.evaluation.eval_pipeline --resume
```

Nếu có Gemini/OpenAI judge và muốn chạy RAGAS thật:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m group_project.evaluation.eval_pipeline --ragas --limit 5
```

Khi không có judge key, báo cáo ghi rõ `Local proxy evaluation — not official RAGAS scores`.

## Tests

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

## Kỹ Thuật Chính

- Chunking: recursive chunk size 800, overlap 100 để giữ ngữ cảnh giữa hai đoạn.
- BGE-M3: cấu hình chính cho embedding đa ngôn ngữ; local hashing fallback giúp demo/test offline không crash.
- ChromaDB: vector store local persistent, dùng cosine distance.
- BM25: có TF saturation và document length normalization, mạnh với năm, mã ngành, điểm số, IELTS/SAT.
- TF-IDF: dùng trọng số term frequency nhân inverse document frequency để so sánh lexical baseline.
- RRF: gộp thứ hạng semantic và BM25 mà không trộn trực tiếp thang điểm khác nhau.
- PageIndex: dùng SDK `PageIndexClient` để upload PDF chính thức, lưu `doc_id` theo fingerprint trong `pageindex_doc_ids.json`, query retrieval/tree API khi khả dụng; nếu lỗi hoặc thiếu key thì local structural fallback parse Markdown theo heading/section.
- Citation: mỗi câu trả lời factual phải trích nguồn từ context, không bịa năm hay điểm chuẩn.

## Troubleshooting

- PDF không extract được text: kiểm tra file có phải scanned PDF không; corpus vẫn có thể dùng nguồn HTML chính thức thay thế.
- Chroma trả dữ liệu cũ: xóa riêng `chroma_db/` rồi chạy lại Task 4.
- Gemini/OpenAI hết quota: hệ thống tự dùng local extractive fallback và ghi `provider=local_extractive`.
- RAGAS 429/quota: chạy `--limit 5` hoặc dùng local proxy.
- Windows Unicode: dùng `python -X utf8` và đặt `PYTHONIOENCODING=utf-8`.
