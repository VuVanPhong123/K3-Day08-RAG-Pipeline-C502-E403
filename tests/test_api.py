from fastapi.testclient import TestClient

import api


client = TestClient(api.app)


def test_health_returns_200():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "index_ready" in data
    assert "chunk_count" in data
    assert "generator" in data


def test_suggestions_returns_list():
    response = client.get("/api/suggestions")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 5


def test_chat_rejects_empty_message():
    response = client.post("/api/chat", json={"message": "   ", "history": [], "top_k": 5})
    assert response.status_code == 422


def test_chat_schema_with_local_fallback(monkeypatch):
    def fake_generate_with_citation(message, top_k=5, history=None, retrieval_options=None):
        return {
            "answer": "Dựa trên tài liệu tuyển sinh. [Nguồn tuyển sinh, 2026]",
            "sources": [
                {
                    "content": "Evidence excerpt",
                    "score": 0.82,
                    "source": "pageindex",
                    "metadata": {
                        "title": "Nguồn tuyển sinh",
                        "institution": "Đại học Bách khoa Hà Nội",
                        "admission_year": 2026,
                        "document_type": "admission_method",
                        "url": "https://ts.hust.edu.vn",
                        "backend": "local_structural_fallback",
                    },
                }
            ],
            "retrieval_source": "pageindex",
            "provider": "local_extractive",
            "model": "local_extractive",
        }

    monkeypatch.setattr(api, "generate_with_citation", fake_generate_with_citation)
    response = client.post("/api/chat", json={"message": "Học phí RMIT?", "history": [], "top_k": 3})
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"answer", "sources", "retrieval_source", "provider", "model"}
    assert data["provider"] == "local_extractive"
    assert data["sources"][0]["metadata"]["backend"] == "local_structural_fallback"


def test_cors_does_not_allow_wildcard_with_credentials():
    assert "*" not in api.get_allowed_origins()
