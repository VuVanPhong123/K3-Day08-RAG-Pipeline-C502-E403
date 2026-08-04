import json
from pathlib import Path

import api
import src.task10_generation as generation
from src.task9_retrieval_pipeline import BGE_M3_THRESHOLD, LOCAL_HASH_THRESHOLD, active_score_threshold


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_contextualize_skips_current_message_when_present():
    history = [
        {"role": "user", "content": "Điều kiện IELTS vào HUST là gì?"},
        {"role": "assistant", "content": "HUST có yêu cầu IELTS theo từng chương trình."},
        {"role": "user", "content": "Còn SAT thì sao?"},
    ]

    contextualized = generation._contextualize_query("Còn SAT thì sao?", history)

    assert contextualized.startswith("Điều kiện IELTS vào HUST")
    assert contextualized.count("Còn SAT thì sao?") == 1


def test_quality_gate_rejects_out_of_domain(monkeypatch):
    monkeypatch.setattr(generation, "retrieve", lambda *args, **kwargs: [])

    result = generation.generate_with_citation("Giá Bitcoin ngày mai là bao nhiêu?")

    assert result["answer"].startswith("I cannot verify this information")
    assert result["provider"] == "quality_gate"


def test_health_reports_configured_and_actual_embedding_backend():
    data = api.health()

    assert "embedding_backend_configured" in data
    assert "embedding_backend_actual" in data
    assert data["embedding_backend"] == data["embedding_backend_actual"]


def test_threshold_is_backend_specific():
    threshold = active_score_threshold()

    assert threshold in {BGE_M3_THRESHOLD, LOCAL_HASH_THRESHOLD}


def test_hust_listing_page_not_primary_score_evidence_if_present():
    for path in (PROJECT_ROOT / "data" / "landing" / "news").glob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("url") == "https://ts.hust.edu.vn/b/diem-chuan-tuyen-sinh":
            assert data.get("page_type") == "listing_page"
            assert data.get("is_primary_evidence") is False


def test_hust_curated_scores_have_program_code_and_score():
    path = PROJECT_ROOT / "data" / "curated" / "hust_admission_scores_2025.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    it1 = [row for row in data["records"] if row["program_code"] == "IT1"]
    assert it1
    assert it1[0]["admission_score"] == 29.19
    assert "evidence" in it1[0]


def test_rmit_tuition_keeps_program_and_fee_in_same_record():
    path = PROJECT_ROOT / "data" / "curated" / "rmit_tuition_fees_2026.json"
    data = json.loads(path.read_text(encoding="utf-8"))

    cs = [row for row in data["records"] if row["program"] == "Computer Science"]
    assert cs
    assert cs[0]["annual_fee_vnd"] == 375840000
    assert cs[0]["whole_program_fee_vnd"] == 1127520000


def test_data_quality_report_flags_no_complete_listing_pages():
    path = PROJECT_ROOT / "data" / "data_quality_report.json"
    if not path.exists():
        return
    report = json.loads(path.read_text(encoding="utf-8"))

    offenders = [
        row["filename"]
        for row in report
        if row.get("page_type") == "listing_page" and row.get("quality_status") == "complete"
    ]
    assert offenders == []
