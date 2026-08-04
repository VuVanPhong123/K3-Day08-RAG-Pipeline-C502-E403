"""Task 9 - Hybrid retrieval pipeline for admission documents."""

from __future__ import annotations

import unicodedata
from concurrent.futures import ThreadPoolExecutor

from .task5_semantic_search import semantic_search
from .task6_lexical_search import lexical_search
from .task7_reranking import rerank, rerank_rrf
from .task8_pageindex_vectorless import pageindex_search
from .task4_chunking_indexing import chunk_documents, embedding_model_actual, load_documents

BGE_M3_THRESHOLD = 0.48
LOCAL_HASH_THRESHOLD = 0.12
SCORE_THRESHOLD = LOCAL_HASH_THRESHOLD
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


def active_score_threshold() -> float:
    actual = embedding_model_actual().lower()
    if "bge-m3" in actual or "baai" in actual:
        return BGE_M3_THRESHOLD
    return LOCAL_HASH_THRESHOLD


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
        item["score"] = float(item.get("score", 0.0)) + (0.05 if matched else -0.05)
        item["metadata"]["institution_boost"] = matched
        boosted.append(item)
    boosted.sort(key=lambda row: row.get("score", 0.0), reverse=True)
    return boosted


def _intent_targets(query: str) -> list[str]:
    folded = _fold(query)
    mapping = [
        (["chi tieu", "quota"], "admission_quota"),
        (["diem chuan", "cutoff", "admission score"], "admission_score"),
        (["hoc phi", "tuition", "fee"], "tuition_fee"),
        (["hoc bong", "scholarship", "financial aid"], "scholarship"),
        (["ho so", "giay to", "dang ky", "apply", "application"], "application"),
        (["ielts", "sat", "act", "a-level", "chung chi", "phuong thuc", "xet tuyen"], "admission_method"),
        (["dieu kien", "entry requirement", "gpa"], "entry_requirement"),
    ]
    return [target for markers, target in mapping if any(marker in folded for marker in markers)]


def _apply_intent_boost(query: str, candidates: list[dict]) -> list[dict]:
    targets = _intent_targets(query)
    if not targets:
        return candidates
    boosted: list[dict] = []
    for item in candidates:
        meta = item.get("metadata", {}) or {}
        meta_text = _fold(
            " ".join(
                str(meta.get(key, ""))
                for key in ("document_type", "type", "title", "source", "source_path", "sub_category")
            )
        )
        matched = any(target in meta_text for target in targets)
        if "admission_method" in targets and any(kind in meta_text for kind in ["admission_regulation", "admission_quota"]):
            matched = True
        incompatible = (
            "admission_score" in meta_text
            and any(target in {"admission_method", "admission_quota", "entry_requirement"} for target in targets)
        )
        item = dict(item)
        item["metadata"] = dict(meta)
        item["score"] = float(item.get("score", 0.0)) + (0.24 if matched else 0.0) - (0.3 if incompatible else 0.0)
        item["metadata"]["intent_boost"] = matched
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
    score_threshold: float | None = None,
    use_reranking: bool = True,
    mode: str = "hybrid",
) -> list[dict]:
    if not isinstance(query, str) or not query.strip():
        return []
    top_k = max(1, min(int(top_k), 20))
    query = query.strip()
    if score_threshold is None:
        score_threshold = active_score_threshold()

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
    merged = _apply_intent_boost(query, _apply_institution_boost(query, merged))

    if _query_targets(query):
        matched = [item for item in merged if item.get("metadata", {}).get("institution_boost")]
        return (matched or merged)[:top_k]

    if use_reranking and merged:
        final = rerank(query, merged, top_k=top_k, method=RERANK_METHOD)
        final = _apply_intent_boost(query, _apply_institution_boost(query, final))
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
