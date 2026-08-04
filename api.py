"""FastAPI backend for the React admission RAG demo."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.task10_generation import GEMINI_MODEL, OPENAI_MODEL, generate_with_citation  # noqa: E402
from src.task4_chunking_indexing import embedding_model_actual, embedding_model_configured, ensure_index_ready, get_collection  # noqa: E402
from src.task8_pageindex_vectorless import pageindex_backend_status  # noqa: E402


SUGGESTIONS = [
    "Điều kiện IELTS vào HUST năm 2026 là gì?",
    "HUST chấp nhận những chứng chỉ quốc tế nào?",
    "Chỉ tiêu ngành Khoa học Máy tính HUST năm 2026 là bao nhiêu?",
    "Học phí Computer Science tại RMIT năm 2026 là bao nhiêu?",
    "VinUni có những chương trình học bổng nào?",
]


class ChatHistoryItem(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatHistoryItem] = Field(default_factory=list, max_length=10)
    top_k: int = Field(default=5, ge=1, le=10)

    @field_validator("message")
    @classmethod
    def message_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message must not be empty")
        return value


def get_allowed_origins() -> list[str]:
    defaults = ["http://localhost:5173", "http://127.0.0.1:5173"]
    configured = os.getenv("FRONTEND_ORIGINS", "")
    origins = defaults + [item.strip() for item in configured.split(",") if item.strip()]
    return sorted({origin for origin in origins if origin != "*"})


def _generator_status() -> dict[str, str]:
    if os.getenv("GEMINI_API_KEY"):
        return {"provider": "gemini", "model": os.getenv("GEMINI_MODEL", GEMINI_MODEL)}
    if os.getenv("OPENAI_API_KEY"):
        return {"provider": "openai", "model": os.getenv("OPENAI_MODEL", OPENAI_MODEL)}
    return {"provider": "local_extractive", "model": "local_extractive"}


def _safe_source(source: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(source.get("metadata", {}) or {})
    safe_metadata = {
        "title": metadata.get("title", ""),
        "institution": metadata.get("institution", ""),
        "admission_year": metadata.get("admission_year", metadata.get("year", "")),
        "document_type": metadata.get("document_type", metadata.get("type", "")),
        "url": metadata.get("url", ""),
        "backend": metadata.get("backend", metadata.get("embedding_model_actual", "")),
        "retrieval_mode": metadata.get("retrieval_mode", metadata.get("fusion_method", "")),
    }
    score = source.get("score", 0.0)
    try:
        score_value = float(score)
    except (TypeError, ValueError):
        score_value = 0.0
    return {
        "content": str(source.get("content", ""))[:2500],
        "score": score_value,
        "source": source.get("source", ""),
        "metadata": safe_metadata,
    }


app = FastAPI(title="University Admission RAG API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/api/health")
def health() -> dict[str, Any]:
    try:
        index_ready = ensure_index_ready()
        chunk_count = get_collection().count() if index_ready else 0
    except Exception:
        index_ready = False
        chunk_count = 0
    return {
        "status": "ok",
        "index_ready": index_ready,
        "chunk_count": chunk_count,
        "generator": _generator_status(),
        "pageindex_backend": pageindex_backend_status(),
        "embedding_backend": embedding_model_actual(),
        "embedding_backend_configured": embedding_model_configured(),
        "embedding_backend_actual": embedding_model_actual(),
    }


@app.get("/api/suggestions")
def suggestions() -> list[str]:
    return SUGGESTIONS


@app.post("/api/chat")
async def chat(request: ChatRequest) -> dict[str, Any]:
    history = [item.model_dump() for item in request.history[-8:]]
    try:
        result = await asyncio.wait_for(
            run_in_threadpool(
                generate_with_citation,
                request.message,
                request.top_k,
                history,
            ),
            timeout=float(os.getenv("API_CHAT_TIMEOUT_SECONDS", "75")),
        )
    except asyncio.TimeoutError as exc:
        raise HTTPException(status_code=504, detail="Request timeout. Vui lòng thử lại với câu hỏi ngắn hơn.") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Không thể xử lý câu hỏi lúc này.") from exc

    return {
        "answer": result.get("answer", "I cannot verify this information"),
        "sources": [_safe_source(source) for source in result.get("sources", [])],
        "retrieval_source": result.get("retrieval_source", "none"),
        "provider": result.get("provider", "unknown"),
        "model": result.get("model", "unknown"),
    }
