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

ALLOWED_DOMAINS = {
    "ts.hust.edu.vn",
    "hust.edu.vn",
    "www.hust.edu.vn",
    "vinuni.edu.vn",
    "www.vinuni.edu.vn",
    "admissions.vinuni.edu.vn",
    "rmit.edu.vn",
    "www.rmit.edu.vn",
    "tuyensinh.hcmus.edu.vn",
    "hcmus.edu.vn",
    "www.hcmus.edu.vn",
}

STOP_MARKERS = [
    "Có thể bạn sẽ thích",
    "Tin xem nhiều",
    "Thông tin liên hệ",
    "Copyright",
    "Các phòng ban",
    "Từ khoá nổi bật",
    "Từ khóa nổi bật",
    "Related posts",
    "You may also like",
    "Share this",
]

MENU_PATTERNS = [
    r"^\s*(trang chủ|giới thiệu|tuyển sinh|đào tạo|nghiên cứu|liên hệ)\s*$",
    r"^\s*(facebook|youtube|linkedin|instagram|twitter|x|zalo)\s*$",
    r"^\s*(đăng nhập|login|register|search|tìm kiếm)\s*$",
    r"^\s*(previous|next|back to top|menu)\s*$",
    r"^\s*(skip to content|search field|rmit australia|rmit europe|students|alumni|staff|library)\s*$",
    r"^\s*(study areas|undergraduate programs|postgraduate programs|pathway programs|student life|about|research)\s*$",
    r"^\s*hotline\s*:?\s*[\d .+-]*\s*$",
]

SPAM_TOKENS = [
    "sv388",
    "sunwin",
    "go88",
    "kubet",
    "tài xỉu",
    "xóc đĩa",
    "casino",
    "bk8",
    "w88",
    "789win",
]

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


def _normalize_text(value: str) -> str:
    value = value.lower()
    value = re.sub(r"\s+", " ", value)
    return value.strip(" #*-:|")


def _visible_match_text(line: str) -> str:
    line = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", line)
    line = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", line)
    line = re.sub(r"https?://\S+", "", line)
    return _normalize_text(line)


def _is_allowed_url(raw_url: str, source_domain: str) -> bool:
    parsed = urlparse(raw_url)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return False
    domain = (parsed.netloc or source_domain).lower().removeprefix("www.")
    if not domain:
        return True
    allowed = {item.removeprefix("www.") for item in ALLOWED_DOMAINS}
    return domain in allowed or domain == source_domain.removeprefix("www.")


def _strip_disallowed_links(line: str, source_domain: str) -> str:
    def replace_markdown(match: re.Match[str]) -> str:
        label, raw_url = match.group(1), match.group(2)
        return match.group(0) if _is_allowed_url(raw_url, source_domain) else label

    line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace_markdown, line)

    def replace_bare(match: re.Match[str]) -> str:
        raw_url = match.group(0)
        return raw_url if _is_allowed_url(raw_url, source_domain) else ""

    return re.sub(r"https?://[^\s)>\]]+", replace_bare, line).strip()


def _line_has_spam(line: str) -> bool:
    lower = _normalize_text(line)
    return any(token in lower for token in SPAM_TOKENS)


def _is_noise_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return True
    if "javascript:void" in stripped.lower():
        return True
    plain = re.sub(r"^[#*\-\s>]+", "", stripped).strip()
    visible = _visible_match_text(plain)
    if re.fullmatch(r"\[?[^\]]+\]?\([^)]+\)", plain) or re.fullmatch(r"https?://\S+", plain):
        return True
    if len(visible) < 12 and not re.search(r"\d|ielts|sat|act|gpa|học phí|tuition|fee|chỉ tiêu|điểm", visible.lower()):
        return True
    if any(re.search(pattern, visible, flags=re.IGNORECASE) for pattern in MENU_PATTERNS):
        return True
    return False


def _find_content_start(lines: list[str], expected_title: str, crawled_title: str) -> int:
    candidates = [_normalize_text(expected_title), _normalize_text(crawled_title)]
    candidates = [item for item in candidates if len(item) >= 12]
    for heading_pattern in [r"^#\s+", r"^#{2,4}\s+"]:
        for index, line in enumerate(lines):
            if not re.match(heading_pattern, line.strip()):
                continue
            normalized = _visible_match_text(line)
            if normalized and any(candidate and (candidate in normalized or normalized in candidate) for candidate in candidates):
                return index
    for index, line in enumerate(lines):
        if line.lstrip().startswith(("*", "-")):
            continue
        normalized = _visible_match_text(line)
        if normalized and any(candidate and (candidate in normalized or normalized in candidate) for candidate in candidates):
            return index
    for index, line in enumerate(lines):
        if re.match(r"^#{1,3}\s+\S", line.strip()):
            return index
    return 0


def _refine_source_start(lines: list[str], start: int, source_url: str, expected_title: str) -> tuple[list[str], int]:
    domain = urlparse(source_url).netloc.lower()
    expected = _normalize_text(expected_title)
    if "rmit.edu.vn" not in domain:
        return lines, start

    markers: list[str] = []
    if "tuition" in expected or "học phí" in expected:
        markers = ["vnd fee", "standard tuition fee", "program fees are priced", "indicative usd fee"]
    elif "application" in expected or "đăng ký" in expected:
        markers = ["## how to apply", "### 1. find your program", "prepare your documents", "submit your application"]
    for index in range(start, len(lines)):
        normalized = _normalize_text(lines[index])
        if any(marker in normalized for marker in markers):
            refined = max(start, index - 3)
            return [f"# {expected_title}", *lines[refined:]], 0
    return lines, start


def sanitize_crawled_markdown(markdown: str, source_url: str, expected_title: str, crawled_title: str = "") -> str:
    """Keep the main admission article body and reject contaminated crawl output."""

    source_domain = urlparse(source_url).netloc.lower()
    if not markdown or not markdown.strip():
        raise ValueError(f"No crawl content extracted from {source_url}")

    raw_lines = [re.sub(r"\s+", " ", line).strip() for line in markdown.splitlines()]
    start = _find_content_start(raw_lines, expected_title, crawled_title)
    raw_lines, start = _refine_source_start(raw_lines, start, source_url, expected_title)
    raw_lines = raw_lines[start:]

    cleaned: list[str] = []
    seen: dict[str, int] = {}
    for line in raw_lines:
        if any(marker.lower() in line.lower() for marker in STOP_MARKERS):
            break
        line = _strip_disallowed_links(line, source_domain)
        if _line_has_spam(line) or _is_noise_line(line):
            continue
        normalized = _normalize_text(line)
        seen[normalized] = seen.get(normalized, 0) + 1
        if seen[normalized] > 2:
            continue
        cleaned.append(line)

    content = "\n\n".join(cleaned).strip()
    normalized_content = _normalize_text(content)
    expected_keywords = [token for token in re.split(r"\W+", _normalize_text(expected_title)) if len(token) >= 3]
    domain_keywords = [
        "tuyển sinh",
        "admission",
        "undergraduate",
        "học phí",
        "tuition",
        "scholarship",
        "học bổng",
        "điểm chuẩn",
        "ielts",
        "chỉ tiêu",
    ]
    has_title_signal = _normalize_text(expected_title) in normalized_content or sum(
        1 for token in expected_keywords if token in normalized_content
    ) >= max(1, min(2, len(expected_keywords)))
    has_domain_signal = any(keyword in normalized_content for keyword in domain_keywords)

    if len(content) <= 500:
        raise ValueError(f"Sanitized content too short from {source_url}")
    if not (has_title_signal or has_domain_signal):
        raise ValueError(f"Sanitized content does not match expected title for {source_url}")
    if any(token in normalized_content for token in SPAM_TOKENS):
        raise ValueError(f"Sanitized content still contains spam tokens from {source_url}")
    return content


def _html_to_markdown(html: str, url: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "form", "footer", "nav", "aside", "header"]):
        tag.decompose()
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else url

    main = (
        soup.find("article")
        or soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.find(class_=re.compile(r"(content|article|post|entry|main)", re.I))
        or soup.body
        or soup
    )
    lines: list[str] = []
    for node in main.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th", "caption"]):
        text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
        if len(text) < 3:
            continue
        if node.name == "h1":
            lines.append(f"# {text}")
        elif node.name == "h2":
            lines.append(f"## {text}")
        elif node.name == "h3":
            lines.append(f"### {text}")
        elif node.name == "h4":
            lines.append(f"#### {text}")
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
    markdown = sanitize_crawled_markdown(markdown, url, source.get("title", ""), title)
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
