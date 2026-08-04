# RAG Evaluation Results

- Run time: 2026-08-04T12:08:47+07:00
- Framework: Local proxy evaluation - not official RAGAS scores
- Judge model: local deterministic proxy
- Corpus fingerprint: 7fa2433a27f8fec481ea6fa95b70b69b
- Test cases: 20

## A/B Metrics

| Metric | Config A | Config B | Delta |
|---|---:|---:|---:|
| faithfulness | 0.7126 | 0.7111 | 0.0015 |
| answer_relevance | 0.1773 | 0.1672 | 0.0101 |
| context_recall | 1.0000 | 0.7082 | 0.2918 |
| context_precision | 1.0000 | 1.0000 | 0.0000 |
| **Average** | **0.7225** | **0.6466** | **0.0758** |

## Bottom 3

| Question | Faithfulness | Relevance | Recall | Precision | Failure stage | Root cause |
|---|---:|---:|---:|---:|---|---|
| Trường nào có ký túc xá tốt nhất cho sinh viên năm nhất? | 0.6194 | 0.0000 | 1.0000 | 1.0000 | Retrieval/grounding | Local hash embedding and noisy web extraction can retrieve broad sections instead of exact evidence. |
| Các mức học bổng merit-based của VinUni cho bậc đại học dao động từ bao nhiêu đến bao nhiêu? | 0.6379 | 0.1032 | 1.0000 | 1.0000 | Retrieval/grounding | Local hash embedding and noisy web extraction can retrieve broad sections instead of exact evidence. |
| Giá Bitcoin ngày mai là bao nhiêu? | 0.7516 | 0.0000 | 1.0000 | 1.0000 | Retrieval/grounding | Local hash embedding and noisy web extraction can retrieve broad sections instead of exact evidence. |

## Recommendations

| Action | Expected impact |
|---|---|
| Enable BAAI/bge-m3 by setting `ADMISSION_RAG_DOWNLOAD_MODELS=1` after model cache is available. | Better multilingual semantic matching for Vietnamese admission questions. |
| Add curated tables for HUST/HCMUS cutoff scores and quotas. | Higher context precision for numeric questions. |
| Run official RAGAS with Gemini/OpenAI judge when quota is available. | Replace proxy metrics with judge-based faithfulness and relevance scores. |
