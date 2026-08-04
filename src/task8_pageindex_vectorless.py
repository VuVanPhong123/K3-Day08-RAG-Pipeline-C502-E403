"""Task 8 - PageIndex API integration with local structural fallback."""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from sklearn.feature_extraction.text import TfidfVectorizer

from .common import now_iso, read_json, tokenize, write_json
from .task4_chunking_indexing import load_documents

load_dotenv()

PAGEINDEX_API_KEY = os.getenv("PAGEINDEX_API_KEY", "")
PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEGAL_DIR = PROJECT_ROOT / "data" / "landing" / "legal"
DOC_IDS_PATH = PROJECT_ROOT / "pageindex_doc_ids.json"
UPLOAD_TIMEOUT_SECONDS = int(os.getenv("PAGEINDEX_UPLOAD_TIMEOUT_SECONDS", "120"))
QUERY_TIMEOUT_SECONDS = int(os.getenv("PAGEINDEX_QUERY_TIMEOUT_SECONDS", "45"))
POLL_SLEEP_SECONDS = float(os.getenv("PAGEINDEX_POLL_SLEEP_SECONDS", "3"))
MAX_POLL_ATTEMPTS = int(os.getenv("PAGEINDEX_MAX_POLL_ATTEMPTS", "12"))


def _safe_pageindex_error(exc: Exception) -> str:
    text = str(exc).lower()
    if any(marker in text for marker in ["api_key", "api key", "unauthorized", "forbidden", "token"]):
        return "PageIndex authentication failed or is not authorized for this operation"
    if "rate" in text or "429" in text:
        return "PageIndex rate limit reached"
    if "timeout" in text:
        return "PageIndex request timed out"
    return "PageIndex API request failed"


def _client():
    from pageindex import PageIndexClient

    return PageIndexClient(api_key=PAGEINDEX_API_KEY)


def _file_fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_registry() -> dict[str, Any]:
    data = read_json(DOC_IDS_PATH, {})
    if not isinstance(data, dict):
        return {}
    data.setdefault("backend", "local_structural_fallback")
    data.setdefault("documents", [])
    return data


def _save_registry(data: dict[str, Any]) -> None:
    data["updated_at"] = now_iso()
    write_json(DOC_IDS_PATH, data)


def _candidate_pdfs() -> list[dict[str, Any]]:
    manifest = read_json(LEGAL_DIR / "sources.json", [])
    candidates: list[dict[str, Any]] = []
    for item in manifest:
        if not isinstance(item, dict):
            continue
        filename = item.get("filename", "")
        path = LEGAL_DIR / filename
        if path.suffix.lower() != ".pdf" or not path.exists():
            continue
        candidates.append(
            {
                "filename": filename,
                "path": path,
                "source_url": item.get("url", ""),
                "institution": item.get("institution", ""),
                "admission_year": item.get("admission_year", ""),
                "fingerprint": _file_fingerprint(path),
            }
        )
    return candidates


def _doc_id_from_response(response: dict[str, Any]) -> str:
    for key in ("doc_id", "document_id", "id"):
        value = response.get(key)
        if value:
            return str(value)
    nested = response.get("document") if isinstance(response.get("document"), dict) else {}
    for key in ("doc_id", "document_id", "id"):
        value = nested.get(key)
        if value:
            return str(value)
    raise ValueError("PageIndex upload response did not include a document id")


def _status_from_response(response: dict[str, Any]) -> str:
    if response.get("retrieval_ready") is True:
        return "completed"
    for key in ("status", "state"):
        value = response.get(key)
        if value:
            text = str(value).lower()
            if text in {"completed", "complete", "ready", "success", "succeeded"}:
                return "completed"
            if text in {"failed", "error"}:
                return "failed"
            return text
    return "processing"


def _poll_document_ready(client: Any, doc_id: str, timeout_seconds: int = UPLOAD_TIMEOUT_SECONDS) -> str:
    deadline = time.monotonic() + timeout_seconds
    sleep_seconds = POLL_SLEEP_SECONDS
    for _ in range(MAX_POLL_ATTEMPTS):
        if time.monotonic() >= deadline:
            return "timeout"
        try:
            tree = client.get_tree(doc_id)
            status = _status_from_response(tree)
            if status in {"completed", "failed"}:
                return status
            metadata = client.get_document(doc_id)
            status = _status_from_response(metadata)
            if status == "failed":
                return status
        except Exception:
            return "api_error"
        time.sleep(min(sleep_seconds, max(0.0, deadline - time.monotonic())))
        sleep_seconds = min(sleep_seconds * 1.5, 12.0)
    return "timeout"


def upload_documents() -> dict[str, Any]:
    """Upload official PDFs to PageIndex when a key is configured."""

    if not PAGEINDEX_API_KEY:
        data = {"backend": "local_structural_fallback", "uploaded": False, "reason": "missing PAGEINDEX_API_KEY", "documents": []}
        _save_registry(data)
        return data

    registry = _load_registry()
    documents = registry.get("documents", [])
    by_filename = {item.get("filename"): item for item in documents if isinstance(item, dict)}
    client = _client()
    uploaded_any = False
    errors: list[str] = []

    for pdf in _candidate_pdfs():
        current = by_filename.get(pdf["filename"], {})
        if current.get("fingerprint") == pdf["fingerprint"] and current.get("status") in {"completed", "api_error", "timeout"}:
            continue
        try:
            response = client.submit_document(str(pdf["path"]))
            doc_id = _doc_id_from_response(response)
            status = _poll_document_ready(client, doc_id)
            by_filename[pdf["filename"]] = {
                "filename": pdf["filename"],
                "source_url": pdf["source_url"],
                "institution": pdf["institution"],
                "admission_year": pdf["admission_year"],
                "fingerprint": pdf["fingerprint"],
                "doc_id": doc_id,
                "status": status,
                "uploaded_at": now_iso(),
                "last_checked_at": now_iso(),
            }
            uploaded_any = True
        except Exception as exc:
            errors.append(_safe_pageindex_error(exc))
            by_filename[pdf["filename"]] = {
                "filename": pdf["filename"],
                "source_url": pdf["source_url"],
                "institution": pdf["institution"],
                "admission_year": pdf["admission_year"],
                "fingerprint": pdf["fingerprint"],
                "doc_id": current.get("doc_id", ""),
                "status": "api_error",
                "uploaded_at": current.get("uploaded_at", ""),
                "last_checked_at": now_iso(),
            }

    completed = [item for item in by_filename.values() if item.get("doc_id") and item.get("status") == "completed"]
    registry = {
        "backend": "pageindex_api" if completed else "local_structural_fallback",
        "uploaded": uploaded_any or bool(completed),
        "documents": list(by_filename.values()),
    }
    if errors:
        registry["reason"] = "; ".join(sorted(set(errors)))
    _save_registry(registry)
    return registry


def pageindex_backend_status() -> str:
    if not PAGEINDEX_API_KEY:
        return "local_structural_fallback"
    registry = _load_registry()
    if any(item.get("status") == "completed" for item in registry.get("documents", [])):
        return "pageindex_api"
    return registry.get("backend", "pageindex_api")


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


def _iter_text_candidates(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        text = ""
        for key in ("content", "text", "markdown", "excerpt", "snippet", "answer"):
            if isinstance(value.get(key), str) and len(value[key].strip()) > len(text):
                text = value[key].strip()
        if text:
            found.append(value)
        for child in value.values():
            found.extend(_iter_text_candidates(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_iter_text_candidates(child))
    return found


def _result_score(item: dict[str, Any], rank: int) -> float:
    for key in ("score", "similarity", "relevance_score"):
        value = item.get(key)
        if isinstance(value, (int, float)):
            return float(value)
    return 1.0 / (rank + 1)


def _content_from_item(item: dict[str, Any]) -> str:
    for key in ("content", "text", "markdown", "excerpt", "snippet", "answer"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return re.sub(r"\s+", " ", value.strip())
    return ""


def _metadata_for_doc(doc: dict[str, Any], item: dict[str, Any]) -> dict[str, Any]:
    section = item.get("section") or item.get("title") or item.get("heading") or ""
    return {
        "source": doc.get("filename", ""),
        "title": item.get("title") or doc.get("filename", ""),
        "institution": doc.get("institution", ""),
        "admission_year": doc.get("admission_year", ""),
        "url": doc.get("source_url", ""),
        "section": section,
        "backend": "pageindex_api",
    }


def _poll_retrieval(client: Any, retrieval_id: str) -> dict[str, Any] | None:
    deadline = time.monotonic() + QUERY_TIMEOUT_SECONDS
    sleep_seconds = POLL_SLEEP_SECONDS
    for _ in range(MAX_POLL_ATTEMPTS):
        if time.monotonic() >= deadline:
            return None
        result = client.get_retrieval(retrieval_id)
        status = _status_from_response(result)
        if status == "completed" or result.get("results") or result.get("retrieval_result"):
            return result
        if status == "failed":
            return None
        time.sleep(min(sleep_seconds, max(0.0, deadline - time.monotonic())))
        sleep_seconds = min(sleep_seconds * 1.5, 8.0)
    return None


def _pageindex_tree_search(client: Any, query: str, docs: list[dict[str, Any]], top_k: int) -> list[dict]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for doc in docs:
        try:
            tree = client.get_tree(str(doc["doc_id"]))
        except Exception:
            continue
        for item in _iter_text_candidates(tree):
            content = _content_from_item(item)
            if len(content) < 80:
                continue
            fingerprint = hashlib.sha256(content[:500].encode("utf-8")).hexdigest()
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            candidates.append({"content": content, "metadata": _metadata_for_doc(doc, item)})

    if not candidates:
        return []
    vectorizer = TfidfVectorizer(tokenizer=tokenize, token_pattern=None, lowercase=False, ngram_range=(1, 2))
    matrix = vectorizer.fit_transform([item["content"] for item in candidates])
    scores = (matrix @ vectorizer.transform([query]).T).toarray().ravel()
    ranked = scores.argsort()[::-1][:top_k]
    results: list[dict] = []
    for rank, idx in enumerate(ranked, 1):
        score = float(scores[idx])
        if score <= 0 and rank > 1:
            continue
        item = candidates[int(idx)]
        results.append(
            {
                "content": item["content"],
                "score": score if score > 0 else 1.0 / (rank + 10),
                "metadata": item["metadata"],
                "source": "pageindex",
            }
        )
    return results[:top_k]


def _pageindex_api_search(query: str, top_k: int) -> list[dict]:
    registry = upload_documents()
    docs = [item for item in registry.get("documents", []) if item.get("doc_id") and item.get("status") == "completed"]
    if not docs:
        return []

    client = _client()
    results: list[dict] = []
    for doc in docs:
        try:
            submission = client.submit_query(str(doc["doc_id"]), query)
            retrieval_id = submission.get("retrieval_id") or submission.get("id")
            if not retrieval_id:
                continue
            retrieval = _poll_retrieval(client, str(retrieval_id))
            if not retrieval:
                continue
        except Exception:
            continue
        for rank, item in enumerate(_iter_text_candidates(retrieval), 1):
            content = _content_from_item(item)
            if len(content) < 40:
                continue
            results.append(
                {
                    "content": content,
                    "score": _result_score(item, rank),
                    "metadata": _metadata_for_doc(doc, item),
                    "source": "pageindex",
                }
            )
    results.sort(key=lambda item: item.get("score", 0.0), reverse=True)
    if results:
        return results[:top_k]
    return _pageindex_tree_search(client, query, docs, top_k)


def pageindex_search(query: str, top_k: int = 5) -> list[dict]:
    top_k = max(1, min(int(top_k), 20))
    if PAGEINDEX_API_KEY:
        try:
            api_results = _pageindex_api_search(query, top_k)
            if api_results:
                return api_results
        except Exception as exc:
            print(f"WARNING: {_safe_pageindex_error(exc)}; using local structural fallback")
    return _local_structural_search(query, top_k)


if __name__ == "__main__":
    for item in pageindex_search("IELTS xét tuyển đại học", top_k=3):
        print(f"[{item['score']:.3f}] {item['metadata'].get('source')} {item['content'][:120]}...")
