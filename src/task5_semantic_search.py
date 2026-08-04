"""Task 5 - Semantic search over ChromaDB."""

from __future__ import annotations

from .task4_chunking_indexing import ensure_index_ready, get_collection, get_embedding_model


def semantic_search(query: str, top_k: int = 10) -> list[dict]:
    if not isinstance(query, str) or not query.strip():
        return []
    top_k = max(1, min(int(top_k), 50))
    if not ensure_index_ready():
        return []

    model = get_embedding_model()
    query_vector = model.encode(query.strip())
    if hasattr(query_vector, "tolist"):
        query_vector = query_vector.tolist()
    collection = get_collection()
    if collection.count() == 0:
        return []

    results = collection.query(
        query_embeddings=[query_vector],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    output: list[dict] = []
    docs = results.get("documents", [[]])[0] or []
    metadatas = results.get("metadatas", [[]])[0] or []
    distances = results.get("distances", [[]])[0] or []
    for doc, meta, distance in zip(docs, metadatas, distances):
        score = max(0.0, min(1.0, 1.0 - float(distance)))
        output.append({"content": doc, "score": float(score), "metadata": dict(meta or {})})

    output.sort(key=lambda item: item["score"], reverse=True)
    return output[:top_k]


if __name__ == "__main__":
    for item in semantic_search("điểm chuẩn ngành công nghệ thông tin năm 2025", top_k=5):
        print(f"[{item['score']:.3f}] {item['metadata'].get('source')} {item['content'][:120]}...")
