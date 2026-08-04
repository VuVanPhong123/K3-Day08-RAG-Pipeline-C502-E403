"""Task 7 - RRF, MMR and optional Jina reranking."""

from __future__ import annotations

import os
from copy import deepcopy

import numpy as np
import requests

from .common import stable_hash, tokenize


def _stable_key(item: dict) -> str:
    meta = item.get("metadata", {}) or {}
    if meta.get("chunk_id"):
        return str(meta["chunk_id"])
    if meta.get("source") and meta.get("chunk_index") is not None:
        return f"{meta['source']}:{meta['chunk_index']}"
    return stable_hash(item.get("content", ""), 20)


def rerank_rrf(ranked_lists: list[list[dict]], top_k: int = 5, k: int = 60) -> list[dict]:
    scores: dict[str, float] = {}
    items: dict[str, dict] = {}
    for ranked_list in ranked_lists:
        for rank, item in enumerate(ranked_list, 1):
            key = _stable_key(item)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            if key not in items:
                items[key] = deepcopy(item)
    ordered = sorted(scores.items(), key=lambda pair: pair[1], reverse=True)
    output: list[dict] = []
    for key, score in ordered[:top_k]:
        item = items[key]
        item["score"] = float(score)
        item.setdefault("metadata", {})["rerank_method"] = "rrf"
        output.append(item)
    return output


def _cosine(a, b) -> float:
    av = np.asarray(a, dtype=float)
    bv = np.asarray(b, dtype=float)
    denom = np.linalg.norm(av) * np.linalg.norm(bv)
    return float(np.dot(av, bv) / denom) if denom else 0.0


def rerank_mmr(
    query_embedding: list[float] | None,
    candidates: list[dict],
    top_k: int = 5,
    lambda_param: float = 0.7,
) -> list[dict]:
    if not candidates:
        return []
    if not query_embedding or not all("embedding" in item for item in candidates):
        return sorted(deepcopy(candidates), key=lambda item: item.get("score", 0.0), reverse=True)[:top_k]

    selected: list[int] = []
    remaining = list(range(len(candidates)))
    while remaining and len(selected) < top_k:
        best_idx = remaining[0]
        best_score = float("-inf")
        for idx in remaining:
            relevance = _cosine(query_embedding, candidates[idx]["embedding"])
            diversity_penalty = max((_cosine(candidates[idx]["embedding"], candidates[j]["embedding"]) for j in selected), default=0.0)
            score = lambda_param * relevance - (1.0 - lambda_param) * diversity_penalty
            if score > best_score:
                best_idx = idx
                best_score = score
        selected.append(best_idx)
        remaining.remove(best_idx)
    results = [deepcopy(candidates[i]) for i in selected]
    for item in results:
        item.setdefault("metadata", {})["rerank_method"] = "mmr"
    return results


def _local_relevance(query: str, content: str) -> float:
    q = set(tokenize(query))
    d = tokenize(content)
    if not q or not d:
        return 0.0
    overlap = sum(1 for token in d if token in q)
    return overlap / max(1, len(q))


def rerank_cross_encoder(query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
    api_key = os.getenv("JINA_API_KEY", "")
    if api_key and candidates:
        try:
            response = requests.post(
                "https://api.jina.ai/v1/rerank",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": os.getenv("JINA_RERANK_MODEL", "jina-reranker-v2-base-multilingual"),
                    "query": query,
                    "documents": [item.get("content", "") for item in candidates],
                    "top_n": min(top_k, len(candidates)),
                },
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()
            results: list[dict] = []
            for row in data.get("results", []):
                item = deepcopy(candidates[int(row["index"])])
                item["score"] = float(row.get("relevance_score", item.get("score", 0.0)))
                item.setdefault("metadata", {})["rerank_method"] = "jina-api"
                results.append(item)
            if results:
                return results[:top_k]
        except Exception as exc:
            print(f"WARNING: Jina reranker failed; using local fallback: {exc}")

    results = []
    for item in deepcopy(candidates):
        item["score"] = float(item.get("score", 0.0)) + _local_relevance(query, item.get("content", ""))
        item.setdefault("metadata", {})["rerank_method"] = "local_overlap"
        results.append(item)
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


def rerank(query: str, candidates: list[dict], top_k: int = 5, method: str = "rrf") -> list[dict]:
    if not candidates:
        return []
    top_k = max(1, min(int(top_k), len(candidates)))
    if method == "cross_encoder":
        return rerank_cross_encoder(query, candidates, top_k)
    if method == "mmr":
        return rerank_mmr(None, candidates, top_k)
    if method == "rrf":
        # For a single candidate list, combine rank signal with a light lexical
        # score so the unified interface is useful in tests and demos.
        base = rerank_rrf([candidates], top_k=len(candidates))
        for item in base:
            item["score"] = float(item.get("score", 0.0)) + _local_relevance(query, item.get("content", ""))
        base.sort(key=lambda item: item["score"], reverse=True)
        return base[:top_k]
    raise ValueError(f"Unknown rerank method: {method}")


if __name__ == "__main__":
    sample = [
        {"content": "Điểm chuẩn ngành Công nghệ thông tin năm 2025", "score": 0.8, "metadata": {}},
        {"content": "Học bổng VinUni từ 50% đến 100% học phí", "score": 0.5, "metadata": {}},
    ]
    print(rerank("điểm chuẩn công nghệ thông tin", sample, top_k=2))
