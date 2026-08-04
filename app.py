"""Streamlit chatbot for University Admission RAG Assistant."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.task10_generation import generate_with_citation  # noqa: E402
from src.task4_chunking_indexing import ensure_index_ready, get_collection  # noqa: E402


st.set_page_config(
    page_title="Trợ lý AI tra cứu tuyển sinh đại học",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


def _provider_status() -> str:
    if os.getenv("GEMINI_API_KEY"):
        return f"Gemini ({os.getenv('GEMINI_MODEL', 'gemini-3.5-flash-lite')})"
    if os.getenv("OPENAI_API_KEY"):
        return f"OpenAI ({os.getenv('OPENAI_MODEL', 'gpt-4o-mini')})"
    return "Local extractive fallback"


@st.cache_data(show_spinner=False, ttl=60)
def _index_status() -> dict:
    ready = ensure_index_ready()
    count = get_collection().count() if ready else 0
    return {"ready": ready, "count": count}


if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_query" not in st.session_state:
    st.session_state.pending_query = None


with st.sidebar:
    st.title("University Admission RAG Assistant")
    st.caption("Trợ lý AI tra cứu tuyển sinh đại học")
    st.divider()

    status = _index_status()
    st.subheader("Trạng thái")
    st.write("Index:", "Sẵn sàng" if status["ready"] else "Chưa sẵn sàng")
    st.write("Chunks:", status["count"])
    st.write("Generator:", _provider_status())
    st.write("PageIndex:", "API" if os.getenv("PAGEINDEX_API_KEY") else "Local structural fallback")

    st.divider()
    top_k = st.slider("Số evidence chunks", 3, 10, 5)

    st.subheader("Câu hỏi gợi ý")
    suggestions = [
        "Điều kiện IELTS vào HUST năm 2026 là gì?",
        "HUST chấp nhận những chứng chỉ quốc tế nào?",
        "Chỉ tiêu ngành Khoa học Máy tính HUST năm 2026 là bao nhiêu?",
        "Học phí Computer Science tại RMIT năm 2026 là bao nhiêu?",
        "VinUni có những chương trình học bổng nào?",
    ]
    for idx, text in enumerate(suggestions):
        if st.button(text, key=f"suggestion_{idx}", use_container_width=True):
            st.session_state.pending_query = text

    st.divider()
    if st.button("Xóa hội thoại", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pending_query = None
        st.rerun()

    if st.session_state.messages:
        export_payload = json.dumps(st.session_state.messages, ensure_ascii=False, indent=2)
        st.download_button("Tải hội thoại", export_payload, "admission_chat_history.json", "application/json")


st.title("Trợ lý AI tra cứu tuyển sinh đại học")
st.caption(
    "Tra cứu điểm chuẩn, phương thức xét tuyển, học phí, học bổng và chỉ tiêu từ nguồn chính thức"
)

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        sources = message.get("sources", [])
        if message["role"] == "assistant" and sources:
            with st.expander(f"Nguồn sử dụng ({len(sources)})"):
                for i, source in enumerate(sources, 1):
                    meta = source.get("metadata", {}) or {}
                    score = source.get("score")
                    score_text = f"{score:.4f}" if isinstance(score, (int, float)) else "n/a"
                    st.markdown(
                        f"**[{i}] {meta.get('title') or meta.get('source', 'Nguồn')}**  \n"
                        f"Trường: `{meta.get('institution', '')}`  \n"
                        f"Năm: `{meta.get('admission_year', meta.get('year', 'n.d.'))}`  \n"
                        f"Loại: `{meta.get('document_type', meta.get('type', 'unknown'))}`  \n"
                        f"Score: `{score_text}` | Retrieval: `{source.get('source', '')}` | Backend: `{meta.get('backend', meta.get('embedding_model_actual', 'hybrid'))}`"
                    )
                    if meta.get("url"):
                        st.link_button("Mở nguồn", meta["url"])
                    st.text_area("Evidence", source.get("content", "")[:1500], height=140, key=f"src_{id(source)}_{i}")


user_input = st.chat_input("Nhập câu hỏi về điểm chuẩn, học phí, học bổng, chỉ tiêu hoặc hồ sơ xét tuyển...")
query = user_input or st.session_state.pending_query

if query:
    st.session_state.pending_query = None
    st.session_state.messages.append({"role": "user", "content": query})

    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("Đang truy xuất tài liệu tuyển sinh và tổng hợp câu trả lời..."):
            try:
                recent_history = [
                    {"role": item["role"], "content": item["content"]}
                    for item in st.session_state.messages[:-1][-8:]
                ]
                response = generate_with_citation(query, top_k=top_k, history=recent_history)
                answer = response.get("answer", "I cannot verify this information")
                sources = response.get("sources", [])
                provider = response.get("provider", "unknown")
                model = response.get("model", "unknown")
            except Exception:
                answer = "I cannot verify this information\n\nCó lỗi khi xử lý câu hỏi. Vui lòng thử lại với câu hỏi cụ thể hơn hoặc kiểm tra trạng thái index."
                sources = []
                provider = "error"
                model = "n/a"

        st.markdown(answer)
        st.caption(f"Provider: {provider} | Model: {model}")
        if sources:
            with st.expander(f"Nguồn sử dụng ({len(sources)})"):
                for i, source in enumerate(sources, 1):
                    meta = source.get("metadata", {}) or {}
                    score = source.get("score")
                    score_text = f"{score:.4f}" if isinstance(score, (int, float)) else "n/a"
                    st.markdown(
                        f"**[{i}] {meta.get('title') or meta.get('source', 'Nguồn')}**  \n"
                        f"Trường: `{meta.get('institution', '')}`  \n"
                        f"Năm: `{meta.get('admission_year', meta.get('year', 'n.d.'))}`  \n"
                        f"Loại: `{meta.get('document_type', meta.get('type', 'unknown'))}`  \n"
                        f"Score: `{score_text}` | Retrieval: `{source.get('source', '')}` | Backend: `{meta.get('backend', meta.get('embedding_model_actual', 'hybrid'))}`"
                    )
                    if meta.get("url"):
                        st.link_button("Mở nguồn", meta["url"], key=f"link_{len(st.session_state.messages)}_{i}")
                    st.text_area("Evidence", source.get("content", "")[:1500], height=140, key=f"evidence_{len(st.session_state.messages)}_{i}")

    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer,
            "sources": sources,
            "provider": provider,
            "model": model,
        }
    )
