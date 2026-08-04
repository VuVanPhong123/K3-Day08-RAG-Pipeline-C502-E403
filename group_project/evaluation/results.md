# RAG Evaluation Results

- Run time: 2026-08-04T10:43:28+07:00
- Framework: Local proxy evaluation — not official RAGAS scores
- Judge model: local deterministic proxy
- Corpus fingerprint: 362c1ef8669d41a967d3e009e9266b25
- Test cases: 15

## A/B Metrics

| Metric | Config A | Config B | Delta |
|---|---:|---:|---:|
| faithfulness | 0.5924 | 0.6959 | -0.1035 |
| answer_relevance | 0.1621 | 0.1551 | 0.0070 |
| context_recall | 0.8343 | 0.5095 | 0.3248 |
| context_precision | 1.0000 | 1.0000 | 0.0000 |
| **Average** | **0.6472** | **0.5901** | **0.0571** |

## Bottom 3

| Question | Faithfulness | Relevance | Recall | Precision | Failure stage | Root cause |
|---|---:|---:|---:|---:|---|---|
| VinUni có chính sách trợ cấp học phí nào cho sinh viên nhập học giai đoạn 2025-2030? | 0.5034 | 0.1183 | 0.0004 | 1.0000 | Retrieval/grounding | Local hash embedding and noisy web extraction can retrieve broad sections instead of exact evidence. |
| Các mức học bổng merit-based của VinUni có thể dao động trong khoảng nào? | 0.6801 | 0.1061 | 0.0138 | 1.0000 | Retrieval/grounding | Local hash embedding and noisy web extraction can retrieve broad sections instead of exact evidence. |
| So sánh học phí đại học VinUni và RMIT Việt Nam theo dữ liệu corpus. | 0.5037 | 0.1644 | 0.5000 | 1.0000 | Retrieval/grounding | Local hash embedding and noisy web extraction can retrieve broad sections instead of exact evidence. |

## Recommendations

| Action | Expected impact |
|---|---|
| Enable BAAI/bge-m3 by setting `ADMISSION_RAG_DOWNLOAD_MODELS=1` after model cache is available. | Better multilingual semantic matching for Vietnamese admission questions. |
| Add curated tables for HUST/HCMUS cutoff scores and quotas. | Higher context precision for numeric questions. |
| Run official RAGAS with Gemini/OpenAI judge when quota is available. | Replace proxy metrics with judge-based faithfulness and relevance scores. |
