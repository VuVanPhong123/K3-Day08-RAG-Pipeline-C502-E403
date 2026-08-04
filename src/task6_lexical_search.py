"""Task 6 - Unicode BM25 and TF-IDF lexical retrieval."""

from __future__ import annotations

from functools import lru_cache

import numpy as np
from rank_bm25 import BM25Okapi
from sklearn.feature_extraction.text import TfidfVectorizer

from .common import tokenize
from .task4_chunking_indexing import chunk_documents, corpus_fingerprint, load_documents


def _load_chunk_corpus() -> list[dict]:
    return chunk_documents(load_documents())


@lru_cache(maxsize=4)
def _cached_indexes(fingerprint: str):
    corpus = _load_chunk_corpus()
    tokenized = [tokenize(item["content"]) for item in corpus]
    bm25 = BM25Okapi(tokenized) if tokenized else None
    tfidf = TfidfVectorizer(
        tokenizer=tokenize,
        token_pattern=None,
        lowercase=False,
        ngram_range=(1, 2),
        min_df=1,
    )
    matrix = tfidf.fit_transform([item["content"] for item in corpus]) if corpus else None
    return corpus, bm25, tfidf, matrix


def build_bm25_index(corpus: list[dict] | None = None):
    data = corpus if corpus is not None else _load_chunk_corpus()
    tokenized = [tokenize(item["content"]) for item in data]
    return BM25Okapi(tokenized) if tokenized else None


def lexical_search(query: str, top_k: int = 10) -> list[dict]:
    if not isinstance(query, str) or not query.strip():
        return []
    top_k = max(1, min(int(top_k), 50))
    corpus, bm25, _, _ = _cached_indexes(corpus_fingerprint())
    if not corpus or bm25 is None:
        return []
    scores = bm25.get_scores(tokenize(query))
    indices = np.argsort(scores)[::-1][:top_k]
    results: list[dict] = []
    for idx in indices:
        score = float(scores[idx])
        if score <= 0:
            continue
        item = corpus[int(idx)]
        results.append(
            {
                "content": item["content"],
                "score": score,
                "metadata": dict(item["metadata"]),
            }
        )
    results.sort(key=lambda item: item["score"], reverse=True)
    return results[:top_k]


def tfidf_search(query: str, top_k: int = 10) -> list[dict]:
    if not isinstance(query, str) or not query.strip():
        return []
    top_k = max(1, min(int(top_k), 50))
    corpus, _, vectorizer, matrix = _cached_indexes(corpus_fingerprint())
    if not corpus or matrix is None:
        return []
    query_vector = vectorizer.transform([query])
    scores = (matrix @ query_vector.T).toarray().ravel()
    indices = np.argsort(scores)[::-1][:top_k]
    results: list[dict] = []
    for idx in indices:
        score = float(scores[idx])
        if score <= 0:
            continue
        item = corpus[int(idx)]
        results.append({"content": item["content"], "score": score, "metadata": dict(item["metadata"])})
    return results[:top_k]


if __name__ == "__main__":
    for item in lexical_search("IELTS xét tuyển Bách khoa Hà Nội 2026", top_k=5):
        print(f"[{item['score']:.3f}] {item['metadata'].get('source')} {item['content'][:120]}...")
