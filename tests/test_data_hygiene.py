from pathlib import Path

import pytest

from src.task2_crawl_news import sanitize_crawled_markdown


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SPAM_TOKENS = ["sv388", "sunwin", "go88", "kubet", "tài xỉu", "xóc đĩa", "casino"]


def test_sanitizer_removes_external_spam_and_menu_noise():
    dirty = """
Trang chủ

Tuyển sinh

# Thông tin tuyển sinh đại học chính quy năm 2026

Đại học Bách khoa Hà Nội thông báo thông tin tuyển sinh đại học chính quy năm 2026.

Thí sinh có chứng chỉ IELTS có thể dùng để quy đổi điểm tiếng Anh theo quy chế tuyển sinh.

Các ngành đào tạo, chỉ tiêu, phương thức xét tuyển và ngưỡng điều kiện được công bố trong đề án.

Nội dung này mô tả lịch đăng ký, điều kiện hồ sơ, quy định minh chứng và hướng dẫn nộp hồ sơ.

Thí sinh cần theo dõi cổng tuyển sinh chính thức để cập nhật mốc thời gian và thông báo mới nhất.

[sv388](https://spam.example/sv388)

Tin xem nhiều

Go88 casino
"""
    cleaned = sanitize_crawled_markdown(
        dirty,
        "https://ts.hust.edu.vn/tin-tuc/thong-tin-tuyen-sinh-dai-hoc-chinh-quy-nam-2026",
        "Thông tin tuyển sinh đại học chính quy năm 2026",
    )

    lower = cleaned.lower()
    assert "trang chủ" not in lower
    assert "spam.example" not in lower
    assert all(token not in lower for token in SPAM_TOKENS)
    assert "Thông tin tuyển sinh đại học chính quy năm 2026" in cleaned


def test_standardized_news_corpus_has_no_spam_tokens():
    paths = list((PROJECT_ROOT / "data" / "standardized" / "news").glob("*.md"))
    if not paths:
        pytest.skip("Standardized news corpus is not generated yet")

    offenders: list[str] = []
    for path in paths:
        text = path.read_text(encoding="utf-8").lower()
        for token in SPAM_TOKENS:
            if token in text:
                offenders.append(f"{path.relative_to(PROJECT_ROOT)} contains {token}")

    assert offenders == []
