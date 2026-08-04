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
User
  -> Streamlit Chatbot
  -> Conversation Memory
  -> Hybrid Retrieval
       -> BGE-M3 + ChromaDB hoặc local hashing embedding fallback
       -> BM25
       -> RRF
       -> Optional Jina
       -> Cosine quality gate
       -> PageIndex/local structural fallback
  -> Context Reordering
  -> Gemini/OpenAI/local extractive generation
  -> Answer + Citations + Sources
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
JINA_API_KEY=
ADMISSION_RAG_DOWNLOAD_MODELS=0
```

Provider priority: Gemini, OpenAI, local extractive fallback. Dự án không dùng OpenRouter.

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

## Chatbot

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

Ứng dụng có chat history, câu hỏi gợi ý, `top_k`, conversation memory, source expander, score, URL, năm tuyển sinh và backend retrieval.

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
.\.venv\Scripts\python.exe -X utf8 -m compileall -q src group_project app.py
.\.venv\Scripts\python.exe -m json.tool group_project/evaluation/golden_dataset.json
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/test_individual.py -v
.\.venv\Scripts\python.exe -X utf8 -m pytest tests/ -v
git diff --check
```

## Kỹ Thuật Chính

- Chunking: recursive chunk size 800, overlap 100 để giữ ngữ cảnh giữa hai đoạn.
- BGE-M3: cấu hình chính cho embedding đa ngôn ngữ; local hashing fallback giúp demo/test offline không crash.
- ChromaDB: vector store local persistent, dùng cosine distance.
- BM25: có TF saturation và document length normalization, mạnh với năm, mã ngành, điểm số, IELTS/SAT.
- TF-IDF: dùng trọng số term frequency nhân inverse document frequency để so sánh lexical baseline.
- RRF: gộp thứ hạng semantic và BM25 mà không trộn trực tiếp thang điểm khác nhau.
- PageIndex fallback: dùng API nếu có key; nếu không, local structural fallback parse Markdown theo heading/section.
- Citation: mỗi câu trả lời factual phải trích nguồn từ context, không bịa năm hay điểm chuẩn.

## Troubleshooting

- PDF không extract được text: kiểm tra file có phải scanned PDF không; corpus vẫn có thể dùng nguồn HTML chính thức thay thế.
- Chroma trả dữ liệu cũ: xóa riêng `chroma_db/` rồi chạy lại Task 4.
- Gemini/OpenAI hết quota: hệ thống tự dùng local extractive fallback và ghi `provider=local_extractive`.
- RAGAS 429/quota: chạy `--limit 5` hoặc dùng local proxy.
- Windows Unicode: dùng `python -X utf8` và đặt `PYTHONIOENCODING=utf-8`.
