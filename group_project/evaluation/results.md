# RAG Evaluation Results

- Run time: 2026-08-04T12:39:06+07:00
- Framework: Local proxy evaluation - not official RAGAS scores
- Judge model: local deterministic proxy
- Corpus fingerprint: e6f6e9a6862c8bd1dc3ccf97a9c9d29d
- Test cases: 18

## A/B Metrics

| Metric | Config A | Config B | Delta |
|---|---:|---:|---:|
| faithfulness | 0.6098 | 0.6355 | -0.0257 |
| answer_relevance | 0.2005 | 0.1955 | 0.0050 |
| context_recall | 0.9444 | 0.6737 | 0.2707 |
| context_precision | 0.9444 | 0.9444 | 0.0000 |
| **Average** | **0.6748** | **0.6123** | **0.0625** |

## Bottom 3

| Question | Faithfulness | Relevance | Recall | Precision | Failure stage | Root cause |
|---|---:|---:|---:|---:|---|---|
| VinUni có trợ cấp học phí cho sinh viên nhập học giai đoạn 2025-2030 không? | 0.0000 | 0.0727 | 0.0000 | 0.0000 | Retrieval/grounding | Local hash embedding and noisy web extraction can retrieve broad sections instead of exact evidence. |
| Các mức học bổng merit-based của VinUni cho bậc đại học dao động từ bao nhiêu đến bao nhiêu? | 0.5714 | 0.0682 | 1.0000 | 1.0000 | Retrieval/grounding | Local hash embedding and noisy web extraction can retrieve broad sections instead of exact evidence. |
| Điều kiện học thuật của Bachelor of Computer Science tại RMIT Việt Nam là gì? | 0.6525 | 0.0921 | 1.0000 | 1.0000 | Retrieval/grounding | Local hash embedding and noisy web extraction can retrieve broad sections instead of exact evidence. |

## Recommendations

| Action | Expected impact |
|---|---|
| Enable BAAI/bge-m3 by setting `ADMISSION_RAG_DOWNLOAD_MODELS=1` after model cache is available. | Better multilingual semantic matching for Vietnamese admission questions. |
| Add curated tables for HUST/HCMUS cutoff scores and quotas. | Higher context precision for numeric questions. |
| Run official RAGAS with Gemini/OpenAI judge when quota is available. | Replace proxy metrics with judge-based faithfulness and relevance scores. |
