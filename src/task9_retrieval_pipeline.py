"""Task 9 - Hybrid retrieval pipeline for admission documents."""

from __future__ import annotations

import unicodedata
from concurrent.futures import ThreadPoolExecutor

from .task5_semantic_search import semantic_search
from .task6_lexical_search import lexical_search
from .task7_reranking import rerank, rerank_rrf
from .task8_pageindex_vectorless import pageindex_search
from .task4_chunking_indexing import chunk_documents, load_documents

SCORE_THRESHOLD = 0.12
DEFAULT_TOP_K = 5
RERANK_METHOD = "rrf"


INSTITUTION_ALIASES = {
    "hust": ["hust", "bach khoa ha noi", "bách khoa hà nội", "dai-hoc-bach-khoa", "đại học bách khoa"],
    "rmit": ["rmit"],
    "vinuni": ["vinuni", "vinuniversity"],
    "hcmus": ["hcmus", "khoa hoc tu nhien", "khoa học tự nhiên", "dhqg-hcm", "đhqg-hcm"],
}


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _query_targets(query: str) -> list[str]:
    folded = _fold(query)
    targets: list[str] = []
    for key, aliases in INSTITUTION_ALIASES.items():
        if any(_fold(alias) in folded for alias in aliases):
            targets.append(key)
    return targets


def _apply_institution_boost(query: str, candidates: list[dict]) -> list[dict]:
    targets = _query_targets(query)
    if not targets:
        return candidates
    boosted: list[dict] = []
    for item in candidates:
        meta = item.get("metadata", {}) or {}
        meta_text = _fold(
            " ".join(
                str(meta.get(key, ""))
                for key in ("institution", "title", "source", "source_path", "url")
            )
        )
        matched = any(any(_fold(alias) in meta_text for alias in INSTITUTION_ALIASES[target]) for target in targets)
        item = dict(item)
        item["metadata"] = dict(meta)
        item["score"] = float(item.get("score", 0.0)) + (10.0 if matched else -2.0)
        item["metadata"]["institution_boost"] = matched
        boosted.append(item)
    boosted.sort(key=lambda row: row.get("score", 0.0), reverse=True)
    return boosted


def _targeted_metadata_search(query: str, top_k: int) -> list[dict]:
    targets = _query_targets(query)
    if not targets:
        return []
    query_tokens = {token for token in _fold(query).split() if len(token) > 1}
    candidates: list[dict] = []
    for chunk in chunk_documents(load_documents()):
        meta = chunk.get("metadata", {}) or {}
        meta_text = _fold(
            " ".join(
                str(meta.get(key, ""))
                for key in ("institution", "title", "source", "source_path", "url")
            )
        )
        if not any(any(_fold(alias) in meta_text for alias in INSTITUTION_ALIASES[target]) for target in targets):
            continue
        content_folded = _fold(chunk.get("content", ""))
        overlap = sum(1 for token in query_tokens if token in content_folded)
        if overlap <= 0:
            continue
        item = dict(chunk)
        item["score"] = float(overlap)
        item["metadata"] = dict(meta)
        item["metadata"]["retrieval_mode"] = "metadata_targeted"
        candidates.append(item)
    candidates.sort(key=lambda row: row.get("score", 0.0), reverse=True)
    return candidates[:top_k]


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
    targeted_results = _targeted_metadata_search(query, top_k * 2)

    best_dense_score = float(dense_results[0]["score"]) if dense_results else 0.0
    if not dense_results or best_dense_score < score_threshold:
        fallback = pageindex_search(query, top_k=top_k)
        if fallback:
            for item in fallback:
                item["source"] = "pageindex"
                item.setdefault("metadata", {})["dense_best_score"] = best_dense_score
                item["metadata"]["score_threshold"] = score_threshold
            return fallback[:top_k]

    merged = rerank_rrf([dense_results, sparse_results, targeted_results], top_k=top_k * 2)
    for item in merged:
        item["source"] = "hybrid"
        item.setdefault("metadata", {})["dense_best_score"] = best_dense_score
        item["metadata"]["fusion_method"] = "rrf"
    merged = _apply_institution_boost(query, merged)

    if _query_targets(query):
        matched = [item for item in merged if item.get("metadata", {}).get("institution_boost")]
        return (matched or merged)[:top_k]

    if use_reranking and merged:
        final = rerank(query, merged, top_k=top_k, method=RERANK_METHOD)
        final = _apply_institution_boost(query, final)
        for item in final:
            item["source"] = "hybrid"
        return final[:top_k]
    return _apply_institution_boost(query, merged)[:top_k]


if __name__ == "__main__":
    for question in [
        "Điều kiện xét tuyển bằng IELTS vào Đại học Bách khoa Hà Nội là gì?",
        "So sánh học phí VinUni và RMIT.",
        "xyzabc123nonsense",
    ]:
        print(f"\nQ: {question}")
        for row in retrieve(question, top_k=3):
            print(f"[{row['score']:.3f}] [{row['source']}] {row['metadata'].get('source')} {row['content'][:90]}...")
