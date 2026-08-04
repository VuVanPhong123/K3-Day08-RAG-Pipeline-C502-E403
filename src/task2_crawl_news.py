"""Task 2 - Crawl official admission information pages into JSON."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .common import configure_utf8, safe_filename, write_json

configure_utf8()

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "landing" / "news"
TIMEOUT = 30
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; UniversityAdmissionRAG/1.0; "
        "+https://example.local/student-project)"
    )
}

ARTICLE_URLS = [
    {
        "url": "https://ts.hust.edu.vn/tin-tuc/thong-tin-tuyen-sinh-dai-hoc-chinh-quy-nam-2026",
        "title": "Thông tin tuyển sinh đại học chính quy năm 2026",
        "institution": "Đại học Bách khoa Hà Nội",
        "category": "admission_quota",
        "admission_year": 2026,
    },
    {
        "url": "https://ts.hust.edu.vn/tin-tuc/quy-che-tuyen-sinh-dai-hoc-nam-2026",
        "title": "Quy chế tuyển sinh đại học năm 2026",
        "institution": "Đại học Bách khoa Hà Nội",
        "category": "admission_method",
        "admission_year": 2026,
    },
    {
        "url": "https://ts.hust.edu.vn/b/diem-chuan-tuyen-sinh",
        "title": "Điểm chuẩn tuyển sinh Đại học Bách khoa Hà Nội",
        "institution": "Đại học Bách khoa Hà Nội",
        "category": "admission_score",
        "admission_year": 2025,
    },
    {
        "url": "https://admissions.vinuni.edu.vn/tuition-fee/undergraduate/",
        "title": "Học phí chương trình đại học VinUniversity",
        "institution": "VinUniversity",
        "category": "tuition_fee",
        "admission_year": 2026,
    },
    {
        "url": "https://admissions.vinuni.edu.vn/scholarship-and-financial-aid/undergraduate-programs/scholarships/",
        "title": "Học bổng và hỗ trợ tài chính bậc đại học VinUniversity",
        "institution": "VinUniversity",
        "category": "scholarship",
        "admission_year": 2026,
    },
    {
        "url": "https://www.rmit.edu.vn/study-at-rmit/tuition-fees",
        "title": "Học phí RMIT Việt Nam",
        "institution": "RMIT Việt Nam",
        "category": "tuition_fee",
        "admission_year": 2026,
    },
    {
        "url": "https://www.rmit.edu.vn/study-at-rmit/undergraduate-programs/apply-for-undergraduate-programs",
        "title": "Đăng ký chương trình đại học RMIT Việt Nam",
        "institution": "RMIT Việt Nam",
        "category": "application_timeline",
        "admission_year": 2026,
    },
    {
        "url": "https://tuyensinh.hcmus.edu.vn/2025-thong-tin-tuyen-sinh/",
        "title": "Thông tin tuyển sinh năm 2025 HCMUS",
        "institution": "Trường Đại học Khoa học tự nhiên, ĐHQG-HCM",
        "category": "admission_method",
        "admission_year": 2025,
    },
]


def setup_directory() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _html_to_markdown(html: str, url: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "form", "footer", "nav"]):
        tag.decompose()
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else url

    main = soup.find("main") or soup.find("article") or soup.body or soup
    lines: list[str] = []
    for node in main.find_all(["h1", "h2", "h3", "p", "li", "td", "th"]):
        text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
        if len(text) < 3:
            continue
        if node.name == "h1":
            lines.append(f"# {text}")
        elif node.name == "h2":
            lines.append(f"## {text}")
        elif node.name == "h3":
            lines.append(f"### {text}")
        elif node.name == "li":
            lines.append(f"- {text}")
        else:
            lines.append(text)
    markdown = "\n\n".join(lines)
    return title, markdown


async def _crawl_with_crawl4ai(url: str) -> tuple[str, str] | None:
    try:
        from crawl4ai import AsyncWebCrawler

        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url)
        markdown = getattr(result, "markdown", "") or ""
        title = ""
        metadata = getattr(result, "metadata", {}) or {}
        if isinstance(metadata, dict):
            title = metadata.get("title", "")
        if len(markdown.strip()) > 500:
            return title or url, markdown.strip()
    except Exception as exc:
        print(f"Crawl4AI fallback for {url}: {exc}")
    return None


def _crawl_with_requests(url: str) -> tuple[str, str]:
    response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if "html" not in content_type.lower() and "text" not in content_type.lower():
        raise ValueError(f"Unsupported content type: {content_type}")
    title, markdown = _html_to_markdown(response.text, url)
    if len(markdown) <= 500:
        raise ValueError(f"Extracted content too short from {url}")
    return title, markdown


async def crawl_article(source: dict) -> dict:
    url = source["url"]
    crawled = await _crawl_with_crawl4ai(url)
    if crawled is None:
        crawled = _crawl_with_requests(url)
    title, markdown = crawled
    return {
        "url": url,
        "title": source.get("title") or title,
        "institution": source["institution"],
        "category": source["category"],
        "admission_year": source["admission_year"],
        "date_crawled": datetime.now().astimezone().isoformat(timespec="seconds"),
        "language": "vi" if ".vn" in urlparse(url).netloc else "en",
        "source_domain": urlparse(url).netloc,
        "content_markdown": markdown,
    }


async def crawl_all() -> list[dict]:
    setup_directory()
    saved: list[dict] = []
    for i, source in enumerate(ARTICLE_URLS, 1):
        try:
            article = await crawl_article(source)
            filename = safe_filename(f"{source['institution']}-{source['category']}-{source['admission_year']}.json")
            path = DATA_DIR / filename
            write_json(path, article)
            if path.stat().st_size <= 500:
                path.unlink(missing_ok=True)
                raise ValueError(f"Output too small: {path}")
            saved.append(article)
            print(f"OK [{i}/{len(ARTICLE_URLS)}] {path.name}")
        except Exception as exc:
            print(f"ERROR [{i}/{len(ARTICLE_URLS)}] {source['url']}: {exc}")

    if len(saved) < 5:
        raise RuntimeError(f"Task 2 requires at least 5 crawled JSON files, got {len(saved)}.")
    return saved


if __name__ == "__main__":
    asyncio.run(crawl_all())
