"""Task 8 - PageIndex vectorless fallback with local structural retrieval."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer

from .common import tokenize
from .task4_chunking_indexing import load_documents

load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOC_IDS_PATH = PROJECT_ROOT / "pageindex_doc_ids.json"


def upload_documents() -> dict:
    """Best-effort PageIndex upload placeholder with persisted status.

    The local structural fallback is the default in offline demo/test mode. This
    function intentionally avoids pretending an upload happened without a key.
    """
    if not PAGEINDEX_API_KEY:
        data = {"backend": "local_structural_fallback", "uploaded": False, "reason": "missing PAGEINDEX_API_KEY"}
        DOC_IDS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return data
    try:
        import pageindex  # noqa: F401

        data = {"backend": "pageindex_api", "uploaded": False, "reason": "SDK upload requires account-specific setup"}
        DOC_IDS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return data
    except Exception as exc:
        data = {"backend": "local_structural_fallback", "uploaded": False, "reason": str(exc)}
        DOC_IDS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return data


def _sections() -> list[dict]:
    sections: list[dict] = []
    for doc in load_documents():
        meta = doc["metadata"]
        current_title = meta.get("title", "")
        buffer: list[str] = []
        for line in doc["content"].splitlines():
            if re.match(r"^#{1,4}\s+", line):
                if buffer:
                    content = "\n".join(buffer).strip()
                    if len(content) > 120:
                        sections.append({"content": content, "metadata": {**meta, "section": current_title}})
                current_title = re.sub(r"^#{1,4}\s+", "", line).strip() or current_title
                buffer = [line]
            else:
                buffer.append(line)
        if buffer:
            content = "\n".join(buffer).strip()
            if len(content) > 120:
                sections.append({"content": content, "metadata": {**meta, "section": current_title}})
    return sections


def _local_structural_search(query: str, top_k: int) -> list[dict]:
    data = _sections()
    if not query.strip() or not data:
        return []
    vectorizer = TfidfVectorizer(tokenizer=tokenize, token_pattern=None, lowercase=False, ngram_range=(1, 2))
    matrix = vectorizer.fit_transform([item["content"] for item in data])
    scores = (matrix @ vectorizer.transform([query]).T).toarray().ravel()
    ranked = scores.argsort()[::-1][:top_k]
    results: list[dict] = []
    for rank, idx in enumerate(ranked, 1):
        score = float(scores[idx])
        if score <= 0 and rank > 1:
            continue
        item = data[int(idx)]
        metadata = dict(item["metadata"])
        metadata["backend"] = "local_structural_fallback"
        results.append(
            {
                "content": item["content"],
                "score": score if score > 0 else 1.0 / (rank + 10),
                "metadata": metadata,
                "source": "pageindex",
            }
        )
    return results[:top_k]


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    top_k = max(1, min(int(top_k), 20))
    if PAGEINDEX_API_KEY:
        # Keep integration explicit and safe; fall back if SDK/account schema is
        # unavailable in this environment.
        try:
            upload_documents()
        except Exception as exc:
            print(f"WARNING: PageIndex API unavailable, using local structural fallback: {exc}")
    return _local_structural_search(query, top_k)


if __name__ == "__main__":
    for item in pageindex_search("IELTS xét tuyển đại học", top_k=3):
        print(f"[{item['score']:.3f}] {item['metadata'].get('source')} {item['content'][:120]}...")
