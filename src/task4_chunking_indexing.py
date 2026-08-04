"""Task 4 - Chunking, embedding and indexing admission documents in ChromaDB."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

import numpy as np
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sklearn.feature_extraction.text import HashingVectorizer
from sklearn.preprocessing import normalize

from .common import configure_utf8, scalar_metadata, stable_hash

configure_utf8()

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STANDARDIZED_DIR = PROJECT_ROOT / "data" / "standardized"
CHROMA_DIR = PROJECT_ROOT / "chroma_db"
FINGERPRINT_PATH = CHROMA_DIR / "corpus_fingerprint.json"

# 800 characters usually holds one meaningful admission-policy unit. An overlap
# of 100 keeps context around cut boundaries. BGE-M3 is multilingual and strong
# for Vietnamese/English admission documents. ChromaDB is local, persistent and
# supports cosine similarity.
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100
CHUNKING_METHOD = "recursive"
EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024
VECTOR_STORE = "chromadb"
COLLECTION_NAME = "university_admission_docs"


class LocalHashEmbeddingModel:
    """Deterministic fallback embedding model for offline tests and demos."""

    name = "local_hashing_vectorizer"
    dimension = EMBEDDING_DIM

    def __init__(self) -> None:
        self.vectorizer = HashingVectorizer(
            n_features=self.dimension,
            alternate_sign=False,
            norm=None,
            lowercase=True,
            analyzer="word",
            token_pattern=r"(?u)\b[\wÀ-ỹ]+(?:[.-][\wÀ-ỹ]+)*\b",
        )

    def encode(self, texts, batch_size: int = 32, show_progress_bar: bool = False):
        single = isinstance(texts, str)
        values = [texts] if single else list(texts)
        matrix = self.vectorizer.transform(values)
        matrix = normalize(matrix, norm="l2", copy=False)
        dense = matrix.astype(np.float32).toarray()
        return dense[0] if single else dense


def _parse_header(content: str) -> tuple[str, dict]:
    lines = content.splitlines()
    title = ""
    metadata: dict[str, str] = {}
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
    for line in lines[1:20]:
        if line.strip() == "---":
            break
        if line.startswith("- ") and ":" in line:
            key, value = line[2:].split(":", 1)
            key = key.strip().lower().replace(" ", "_")
            metadata[key] = value.strip()
    return title, metadata


def corpus_fingerprint() -> str:
    h = stable_hash("admission-corpus", 64)
    parts: list[str] = []
    for path in sorted(STANDARDIZED_DIR.rglob("*.md")):
        stat = path.stat()
        parts.append(f"{path.relative_to(STANDARDIZED_DIR)}:{stat.st_size}:{stat.st_mtime_ns}")
    return stable_hash("\n".join(parts) or h, 32)


def load_documents() -> list[dict]:
    documents: list[dict] = []
    for path in sorted(STANDARDIZED_DIR.rglob("*.md")):
        content = path.read_text(encoding="utf-8")
        if len(content.strip()) <= 200:
            continue
        title, header = _parse_header(content)
        doc_type = header.get("document_type") or header.get("category") or path.parent.name
        url = header.get("source", "")
        metadata = {
            "source": path.name,
            "source_path": str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"),
            "title": title or path.stem,
            "institution": header.get("institution", ""),
            "document_type": doc_type,
            "type": doc_type,
            "admission_year": header.get("admission_year", ""),
            "year": header.get("admission_year", ""),
            "url": url,
        }
        documents.append({"content": content, "metadata": metadata})
    return documents


def chunk_documents(documents: list[dict]) -> list[dict]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", "; ", ", ", " ", ""],
    )
    chunks: list[dict] = []
    for doc in documents:
        splits = splitter.split_text(doc["content"])
        for index, text in enumerate(splits):
            text = text.strip()
            if len(text) < 60:
                continue
            chunk_id = stable_hash(f"{doc['metadata']['source_path']}:{index}:{text[:80]}", 20)
            metadata = {
                **doc["metadata"],
                "chunk_index": index,
                "chunk_id": chunk_id,
            }
            chunks.append({"content": text, "metadata": metadata})
    return chunks


@lru_cache(maxsize=1)
def get_embedding_model():
    if os.getenv("ADMISSION_RAG_DOWNLOAD_MODELS", "0") == "1":
        try:
            from sentence_transformers import SentenceTransformer

            model_name = os.getenv("EMBEDDING_MODEL", EMBEDDING_MODEL)
            model = SentenceTransformer(model_name)
            model.name = model_name
            model.dimension = EMBEDDING_DIM
            return model
        except Exception as exc:
            print(f"WARNING: cannot load {EMBEDDING_MODEL}; using local fallback: {exc}")
    return LocalHashEmbeddingModel()


def _to_list(vector) -> list[float]:
    if hasattr(vector, "tolist"):
        return vector.tolist()
    return list(vector)


def embed_chunks(chunks: list[dict]) -> list[dict]:
    model = get_embedding_model()
    texts = [chunk["content"] for chunk in chunks]
    embeddings = model.encode(texts, batch_size=32, show_progress_bar=False)
    for chunk, embedding in zip(chunks, embeddings):
        chunk["embedding"] = _to_list(embedding)
        chunk["metadata"]["embedding_model_actual"] = getattr(model, "name", EMBEDDING_MODEL)
    return chunks


def get_chroma_client():
    import chromadb

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(CHROMA_DIR))


def get_collection():
    client = get_chroma_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine", "domain": "university_admission"},
    )


def index_to_vectorstore(chunks: list[dict], rebuild: bool = False):
    client = get_chroma_client()
    if rebuild:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception as exc:
            print(f"Chroma collection recreate note: {exc}")
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine", "domain": "university_admission"},
    )
    ids = [chunk["metadata"]["chunk_id"] for chunk in chunks]
    for start in range(0, len(chunks), 128):
        batch = chunks[start : start + 128]
        collection.upsert(
            ids=ids[start : start + 128],
            documents=[chunk["content"] for chunk in batch],
            embeddings=[chunk["embedding"] for chunk in batch],
            metadatas=[scalar_metadata(chunk["metadata"]) for chunk in batch],
        )
    FINGERPRINT_PATH.write_text(
        json.dumps(
            {
                "fingerprint": corpus_fingerprint(),
                "collection": COLLECTION_NAME,
                "embedding_model_configured": EMBEDDING_MODEL,
                "embedding_model_actual": getattr(get_embedding_model(), "name", EMBEDDING_MODEL),
                "chunk_size": CHUNK_SIZE,
                "chunk_overlap": CHUNK_OVERLAP,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return collection


def ensure_index_ready() -> bool:
    docs = load_documents()
    if not docs:
        return False
    current_fp = corpus_fingerprint()
    stored = {}
    if FINGERPRINT_PATH.exists():
        stored = json.loads(FINGERPRINT_PATH.read_text(encoding="utf-8"))
    try:
        collection = get_collection()
        count = collection.count()
    except Exception:
        count = 0
    if count == 0 or stored.get("fingerprint") != current_fp:
        run_pipeline(rebuild=True)
    return True


def run_pipeline(rebuild: bool = True):
    print("Task 4: Chunking and indexing")
    docs = load_documents()
    print(f"Loaded {len(docs)} documents")
    chunks = chunk_documents(docs)
    print(f"Created {len(chunks)} chunks")
    embed_chunks(chunks)
    collection = index_to_vectorstore(chunks, rebuild=rebuild)
    print(f"Indexed {collection.count()} chunks into {COLLECTION_NAME}")
    return collection


if __name__ == "__main__":
    run_pipeline(rebuild=True)
