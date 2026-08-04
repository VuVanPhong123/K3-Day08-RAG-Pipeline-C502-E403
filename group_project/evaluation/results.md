# RAG Evaluation Results

- Run time: 2026-08-04T11:46:51+07:00
- Framework: Local proxy evaluation — not official RAGAS scores
- Judge model: local deterministic proxy
- Corpus fingerprint: c6d51ccfd447eee611e4d39fe2b22b7d
- Test cases: 2

## A/B Metrics

| Metric | Config A | Config B | Delta |
|---|---:|---:|---:|
| faithfulness | 0.7504 | 0.6794 | 0.0710 |
| answer_relevance | 0.1854 | 0.2122 | -0.0268 |
| context_recall | 1.0000 | 1.0000 | 0.0000 |
| context_precision | 1.0000 | 1.0000 | 0.0000 |
| **Average** | **0.7339** | **0.7229** | **0.0111** |

## Bottom 3

| Question | Faithfulness | Relevance | Recall | Precision | Failure stage | Root cause |
|---|---:|---:|---:|---:|---|---|
| Đại học Bách khoa Hà Nội dự kiến tuyển bao nhiêu sinh viên đại học chính quy năm 2026? | 0.6940 | 0.1895 | 1.0000 | 1.0000 | Retrieval/grounding | Local hash embedding and noisy web extraction can retrieve broad sections instead of exact evidence. |
| HUST sử dụng những nhóm phương thức xét tuyển chính nào trong năm 2026? | 0.8068 | 0.1813 | 1.0000 | 1.0000 | Retrieval/grounding | Local hash embedding and noisy web extraction can retrieve broad sections instead of exact evidence. |

## Recommendations

| Action | Expected impact |
|---|---|
| Enable BAAI/bge-m3 by setting `ADMISSION_RAG_DOWNLOAD_MODELS=1` after model cache is available. | Better multilingual semantic matching for Vietnamese admission questions. |
| Add curated tables for HUST/HCMUS cutoff scores and quotas. | Higher context precision for numeric questions. |
| Run official RAGAS with Gemini/OpenAI judge when quota is available. | Replace proxy metrics with judge-based faithfulness and relevance scores. |
