"""Task 9 - Hybrid retrieval pipeline for admission documents."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from .task5_semantic_search import semantic_search
from .task6_lexical_search import lexical_search
from .task7_reranking import rerank, rerank_rrf
from .task8_pageindex_vectorless import pageindex_search

SCORE_THRESHOLD = 0.48
DEFAULT_TOP_K = 5
RERANK_METHOD = "rrf"


def retrieve(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    score_threshold: float = SCORE_THRESHOLD,
    use_reranking: bool = True,
    mode: str = "hybrid",
) -> list[dict]:
    if not isinstance(query, str) or not query.strip():
        return []
    top_k = max(1, min(int(top_k), 20))
    query = query.strip()

    if mode == "dense_only":
        dense = semantic_search(query, top_k=top_k)
        for item in dense:
            item["source"] = "hybrid"
            item.setdefault("metadata", {})["retrieval_mode"] = "dense_only"
        return dense[:top_k]

    with ThreadPoolExecutor(max_workers=2) as executor:
        dense_future = executor.submit(semantic_search, query, top_k * 2)
        sparse_future = executor.submit(lexical_search, query, top_k * 2)
        dense_results = dense_future.result()
        sparse_results = sparse_future.result()

    best_dense_score = float(dense_results[0]["score"]) if dense_results else 0.0
    if not dense_results or best_dense_score < score_threshold:
        fallback = pageindex_search(query, top_k=top_k)
        if fallback:
            for item in fallback:
                item["source"] = "pageindex"
                item.setdefault("metadata", {})["dense_best_score"] = best_dense_score
                item["metadata"]["score_threshold"] = score_threshold
            return fallback[:top_k]

    merged = rerank_rrf([dense_results, sparse_results], top_k=top_k * 2)
    for item in merged:
        item["source"] = "hybrid"
        item.setdefault("metadata", {})["dense_best_score"] = best_dense_score
        item["metadata"]["fusion_method"] = "rrf"

    if use_reranking and merged:
        final = rerank(query, merged, top_k=top_k, method=RERANK_METHOD)
        for item in final:
            item["source"] = "hybrid"
        return final[:top_k]
    return merged[:top_k]


if __name__ == "__main__":
    for question in [
        "Điều kiện xét tuyển bằng IELTS vào Đại học Bách khoa Hà Nội là gì?",
        "So sánh học phí VinUni và RMIT.",
        "xyzabc123nonsense",
    ]:
        print(f"\nQ: {question}")
        for row in retrieve(question, top_k=3):
            print(f"[{row['score']:.3f}] [{row['source']}] {row['metadata'].get('source')} {row['content'][:90]}...")
