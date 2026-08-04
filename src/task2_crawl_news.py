"""Task 2 - Crawl official admission information pages into JSON."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse, urldefrag

import requests
import urllib3
from bs4 import BeautifulSoup

from .common import configure_utf8, safe_filename, write_json

configure_utf8()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "landing" / "news"
QUALITY_REPORT_PATH = PROJECT_ROOT / "data" / "data_quality_report.json"
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
    "Cổng thông tin tuyển sinh Trường Đại học Khoa học tự nhiên",
]

MENU_PATTERNS = [
    r"^\s*(trang chủ|giới thiệu|tuyển sinh|đào tạo|nghiên cứu|liên hệ)\s*$",
    r"^\s*(facebook|youtube|linkedin|instagram|twitter|x|zalo)\s*$",
    r"^\s*(đăng nhập|login|register|search|tìm kiếm)\s*$",
    r"^\s*(previous|next|back to top|menu|skip to content|arrow icon)\s*$",
    r"^\s*(search field|rmit australia|rmit europe|students|alumni|staff|library)\s*$",
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
        "sub_category": "quota_and_methods",
        "admission_year": 2026,
        "page_type": "detail_page",
        "is_primary_evidence": True,
    },
    {
        "url": "https://ts.hust.edu.vn/tin-tuc/quy-che-tuyen-sinh-dai-hoc-nam-2026",
        "title": "Quy chế tuyển sinh đại học năm 2026",
        "institution": "Đại học Bách khoa Hà Nội",
        "category": "admission_method",
        "sub_category": "regulation_pointer",
        "admission_year": 2026,
        "page_type": "document_pointer",
        "is_primary_evidence": False,
    },
    {
        "url": "https://ts.hust.edu.vn/tin-tuc/quy-dinh-ve-phuong-thuc-xet-tuyen-tai-nang-nam-2026",
        "title": "Quy định về Phương thức Xét tuyển tài năng năm 2026",
        "institution": "Đại học Bách khoa Hà Nội",
        "category": "admission_method",
        "sub_category": "talent_admission",
        "admission_year": 2026,
        "page_type": "document_pointer",
        "is_primary_evidence": False,
        "allow_short": True,
        "parent_url": "https://ts.hust.edu.vn/tin-tuc/quy-che-tuyen-sinh-dai-hoc-nam-2026",
        "discovered_from": "document pointer link text: TẠI ĐÂY",
    },
    {
        "url": "https://ts.hust.edu.vn/tin-tuc/diem-chuan-cao-nhat-dh-bach-khoa-ha-noi-2025-29-39-diem-thpt-tuong-duong-93-96-diem-xttn-va-86-97-diem-tsa",
        "title": "Điểm chuẩn cao nhất ĐH Bách khoa Hà Nội 2025",
        "institution": "Đại học Bách khoa Hà Nội",
        "category": "admission_score",
        "sub_category": "cutoff_2025_article",
        "admission_year": 2025,
        "page_type": "detail_page",
        "is_primary_evidence": True,
        "parent_url": "https://ts.hust.edu.vn/b/diem-chuan-tuyen-sinh",
        "discovered_from": "listing page /b/diem-chuan-tuyen-sinh",
    },
    {
        "url": "https://admissions.vinuni.edu.vn/tuition-fee/undergraduate/",
        "title": "Học phí chương trình đại học VinUniversity",
        "institution": "VinUniversity",
        "category": "tuition_fee",
        "sub_category": "undergraduate_tuition",
        "admission_year": 2026,
        "page_type": "table_page",
        "is_primary_evidence": True,
    },
    {
        "url": "https://admissions.vinuni.edu.vn/scholarship-and-financial-aid/undergraduate-programs/scholarships/",
        "title": "Học bổng và hỗ trợ tài chính bậc đại học VinUniversity",
        "institution": "VinUniversity",
        "category": "scholarship",
        "sub_category": "undergraduate_scholarship",
        "admission_year": 2026,
        "page_type": "detail_page",
        "is_primary_evidence": True,
    },
    {
        "url": "https://www.rmit.edu.vn/study-at-rmit/tuition-fees",
        "title": "Học phí RMIT Việt Nam",
        "institution": "RMIT Việt Nam",
        "category": "tuition_fee",
        "sub_category": "tuition_table",
        "admission_year": 2026,
        "page_type": "table_page",
        "is_primary_evidence": True,
    },
    {
        "url": "https://www.rmit.edu.vn/study-at-rmit/undergraduate-programs/apply-for-undergraduate-programs",
        "title": "Đăng ký chương trình đại học RMIT Việt Nam",
        "institution": "RMIT Việt Nam",
        "category": "application_process",
        "sub_category": "general_application_process",
        "admission_year": 2026,
        "page_type": "detail_page",
        "is_primary_evidence": True,
    },
    {
        "url": "https://www.rmit.edu.vn/study-at-rmit/important-dates-for-students",
        "title": "Important dates for students RMIT Việt Nam",
        "institution": "RMIT Việt Nam",
        "category": "application_timeline",
        "sub_category": "important_dates",
        "admission_year": 2026,
        "page_type": "document_pointer",
        "is_primary_evidence": False,
        "parent_url": "https://www.rmit.edu.vn/study-at-rmit/undergraduate-programs",
    },
    {
        "url": "https://www.rmit.edu.vn/study-at-rmit/undergraduate-programs/bachelor-of-computer-science",
        "title": "Bachelor of Computer Science RMIT Việt Nam",
        "institution": "RMIT Việt Nam",
        "category": "entry_requirement",
        "sub_category": "computer_science",
        "admission_year": 2026,
        "page_type": "detail_page",
        "is_primary_evidence": True,
        "parent_url": "https://www.rmit.edu.vn/study-at-rmit/undergraduate-programs",
    },
    {
        "url": "https://tuyensinh.hcmus.edu.vn/2025-thong-tin-tuyen-sinh/",
        "title": "Thông tin tuyển sinh năm 2025 HCMUS",
        "institution": "Trường Đại học Khoa học tự nhiên, ĐHQG-HCM",
        "category": "admission_method",
        "sub_category": "overview",
        "admission_year": 2025,
        "page_type": "document_pointer",
        "is_primary_evidence": False,
    },
    {
        "url": "https://tuyensinh.hcmus.edu.vn/thong-bao-ve-phuong-thuc-xet-tuyen-1b-va-1c-nam-2025/",
        "title": "Thông báo về phương thức xét tuyển 1B và 1C năm 2025 HCMUS",
        "institution": "Trường Đại học Khoa học tự nhiên, ĐHQG-HCM",
        "category": "admission_method",
        "sub_category": "vnuhcm_priority",
        "admission_year": 2025,
        "page_type": "detail_page",
        "is_primary_evidence": True,
        "parent_url": "https://tuyensinh.hcmus.edu.vn/2025-thong-tin-tuyen-sinh/",
    },
    {
        "url": "https://tuyensinh.hcmus.edu.vn/2025-thong-bao-ve-phuong-thuc-xet-tuyen-1d/",
        "title": "Thông báo về phương thức xét tuyển 1D năm 2025 HCMUS",
        "institution": "Trường Đại học Khoa học tự nhiên, ĐHQG-HCM",
        "category": "admission_method",
        "sub_category": "international_certificate",
        "admission_year": 2025,
        "page_type": "detail_page",
        "is_primary_evidence": True,
        "parent_url": "https://tuyensinh.hcmus.edu.vn/2025-thong-tin-tuyen-sinh/",
    },
    {
        "url": "https://tuyensinh.hcmus.edu.vn/thong-bao-ve-phuong-thuc-xet-tuyen-2-va-3-nam-2025/",
        "title": "Thông báo về phương thức xét tuyển 2 và 3 năm 2025 HCMUS",
        "institution": "Trường Đại học Khoa học tự nhiên, ĐHQG-HCM",
        "category": "admission_method",
        "sub_category": "thpt_and_dgnl",
        "admission_year": 2025,
        "page_type": "detail_page",
        "is_primary_evidence": True,
        "parent_url": "https://tuyensinh.hcmus.edu.vn/2025-thong-tin-tuyen-sinh/",
    },
    {
        "url": "https://tuyensinh.hcmus.edu.vn/2025-diem-chuan-cac-phuong-thuc/",
        "title": "Điểm chuẩn các phương thức xét tuyển năm 2025 HCMUS",
        "institution": "Trường Đại học Khoa học tự nhiên, ĐHQG-HCM",
        "category": "admission_score",
        "sub_category": "cutoff_2025",
        "admission_year": 2025,
        "page_type": "document_pointer",
        "is_primary_evidence": False,
        "allow_short": True,
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


def _allowed_domain(raw_url: str, source_domain: str) -> bool:
    parsed = urlparse(raw_url)
    if parsed.scheme and parsed.scheme not in {"http", "https"}:
        return False
    domain = (parsed.netloc or source_domain).lower().removeprefix("www.")
    allowed = {item.removeprefix("www.") for item in ALLOWED_DOMAINS}
    return not domain or domain in allowed or domain == source_domain.removeprefix("www.")


def _strip_disallowed_links(line: str, source_domain: str) -> str:
    def replace_markdown(match: re.Match[str]) -> str:
        label, raw_url = match.group(1), match.group(2)
        return match.group(0) if _allowed_domain(raw_url, source_domain) else label

    line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace_markdown, line)

    def replace_bare(match: re.Match[str]) -> str:
        raw_url = match.group(0)
        return raw_url if _allowed_domain(raw_url, source_domain) else ""

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
    return any(re.search(pattern, visible, flags=re.IGNORECASE) for pattern in MENU_PATTERNS)


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
        normalized = _visible_match_text(line)
        if normalized and any(candidate and (candidate in normalized or normalized in candidate) for candidate in candidates):
            return index
    for index, line in enumerate(lines):
        if re.match(r"^#{1,3}\s+\S", line.strip()):
            return index
    return 0


def _markdown_table(table) -> list[str]:
    rows: list[list[str]] = []
    for tr in table.find_all("tr"):
        cells = [re.sub(r"\s+", " ", cell.get_text(" ", strip=True)).strip() for cell in tr.find_all(["th", "td"])]
        if cells and any(cells):
            rows.append(cells)
    if not rows:
        return []
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    output = [
        "| " + " | ".join(rows[0]) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    output.extend("| " + " | ".join(row) + " |" for row in rows[1:])
    return output


def _html_to_markdown(html: str, url: str) -> tuple[str, str, dict]:
    soup = BeautifulSoup(html, "html.parser")
    link_count = len(soup.find_all("a", href=True))
    heading_count = len(soup.find_all(re.compile(r"^h[1-6]$")))
    tables = soup.find_all("table")
    table_rows = sum(len(table.find_all("tr")) for table in tables)
    for tag in soup(["script", "style", "noscript", "svg", "form", "footer", "nav", "aside", "header"]):
        tag.decompose()

    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else url

    def collect_lines(main_node) -> list[str]:
        collected: list[str] = []
        for node in main_node.find_all(["h1", "h2", "h3", "h4", "p", "li", "table"], recursive=True):
            if node.find_parent("table") and node.name != "table":
                continue
            if node.name == "table":
                collected.extend(_markdown_table(node))
                continue
            text = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
            if len(text) < 3:
                continue
            if node.name == "h1":
                collected.append(f"# {text}")
            elif node.name == "h2":
                collected.append(f"## {text}")
            elif node.name == "h3":
                collected.append(f"### {text}")
            elif node.name == "h4":
                collected.append(f"#### {text}")
            elif node.name == "li":
                collected.append(f"- {text}")
            else:
                collected.append(text)
        return collected

    main = (
        soup.find("article")
        or soup.find("main")
        or soup.find(attrs={"role": "main"})
        or soup.find(class_=re.compile(r"(content|article|post|entry|main)", re.I))
        or soup.body
        or soup
    )
    lines = collect_lines(main)
    if len("\n\n".join(lines)) <= 500 and soup.body is not None and main is not soup.body:
        lines = collect_lines(soup.body)
    stats = {
        "visible_text_characters": len(soup.get_text(" ", strip=True)),
        "link_count": link_count,
        "heading_count": heading_count,
        "table_count": len(tables),
        "table_rows": table_rows,
    }
    return title, "\n\n".join(lines), stats


def sanitize_crawled_markdown(markdown: str, source_url: str, expected_title: str, crawled_title: str = "", min_chars: int = 500) -> str:
    """Keep the main admission body and reject contaminated crawl output."""

    source_domain = urlparse(source_url).netloc.lower()
    if not markdown or not markdown.strip():
        raise ValueError(f"No crawl content extracted from {source_url}")

    raw_lines = [re.sub(r"\s+", " ", line).strip() for line in markdown.splitlines()]
    start = _find_content_start(raw_lines, expected_title, crawled_title)
    raw_lines = raw_lines[start:]

    cleaned: list[str] = []
    seen: dict[str, int] = {}
    for line in raw_lines:
        if any(marker.lower() in line.lower() for marker in STOP_MARKERS):
            break
        line = _strip_disallowed_links(line, source_domain)
        if _line_has_spam(line) or _is_noise_line(line):
            continue
        if "|" in line and "Ö" in line:
            line = line.replace("Ö", "Có")
        normalized = _normalize_text(line)
        seen[normalized] = seen.get(normalized, 0) + 1
        if seen[normalized] > 2:
            continue
        cleaned.append(line.replace(";(1.3)", ";\n\n(1.3)").replace("Trong đó:-", "Trong đó:\n- ").replace("+)", "\n+) "))

    content = "\n\n".join(cleaned).strip()
    normalized_content = _normalize_text(content)
    domain_keywords = [
        "tuyển sinh",
        "admission",
        "undergraduate",
        "học phí",
        "tuition",
        "scholarship",
        "học bổng",
        "điểm chuẩn",
        "xét tuyển",
        "ielts",
        "chỉ tiêu",
    ]
    if len(content) <= min_chars:
        raise ValueError(f"Sanitized content too short from {source_url}")
    if not any(keyword in normalized_content for keyword in domain_keywords):
        raise ValueError(f"Sanitized content does not look like admission content from {source_url}")
    if any(token in normalized_content for token in SPAM_TOKENS):
        raise ValueError(f"Sanitized content still contains spam tokens from {source_url}")
    return content


def detect_page_type(markdown: str, source_url: str, link_count: int) -> str:
    lower = _normalize_text(markdown)
    url_lower = source_url.lower()
    pointer_terms = ["tại đây", "xem tại đây", "download", "chi tiết tại", ".pdf"]
    listing_terms = ["tin tức", "điểm chuẩn các năm", "xem tất cả", "b/diem-chuan"]
    if "|" in markdown and re.search(r"\|\s*---", markdown):
        return "table_page"
    if len(markdown) < 3500 and any(term in lower for term in pointer_terms):
        return "document_pointer"
    date_count = len(re.findall(r"\b\d{1,2}[-/]\d{1,2}[-/]\d{4}\b|\b\d{1,2}-\d{1,2}-\d{4}\b", markdown))
    if link_count >= 15 and (date_count >= 3 or any(term in lower or term in url_lower for term in listing_terms)):
        return "listing_page"
    if link_count >= 10 and any(term in lower for term in pointer_terms):
        return "mixed_page"
    return "detail_page"


def discover_relevant_child_sources(html: str, source_url: str, max_child_sources_per_parent: int = 10) -> list[dict]:
    source_domain = urlparse(source_url).netloc.lower().removeprefix("www.")
    soup = BeautifulSoup(html, "html.parser")
    keywords = [
        "quy chế tuyển sinh",
        "phương thức xét tuyển",
        "xét tuyển tài năng",
        "điểm chuẩn",
        "chỉ tiêu",
        "học phí",
        "application checklist",
        "important dates",
        "entry requirements",
        "phụ lục",
        "tại đây",
    ]
    skipped = ["facebook", "twitter", "zalo", "login", "javascript:", "mailto:", "tel:", "trang chủ"]
    children: list[dict] = []
    seen: set[str] = set()
    for link in soup.find_all("a", href=True):
        label = re.sub(r"\s+", " ", link.get_text(" ", strip=True)).strip()
        href = urldefrag(urljoin(source_url, link["href"]))[0]
        combined = f"{label} {href}".lower()
        parsed = urlparse(href)
        domain = parsed.netloc.lower().removeprefix("www.")
        if not href or href in seen:
            continue
        if domain and domain != source_domain and domain not in {d.removeprefix("www.") for d in ALLOWED_DOMAINS}:
            continue
        if any(term in combined for term in skipped):
            continue
        if not any(term in combined for term in keywords):
            continue
        if re.search(r"\.(jpg|jpeg|png|gif|webp)$", parsed.path, flags=re.I):
            continue
        seen.add(href)
        children.append({"url": href, "anchor_text": label, "parent_url": source_url})
        if len(children) >= max_child_sources_per_parent:
            break
    return children


async def _crawl_with_crawl4ai(url: str) -> tuple[str, str, dict] | None:
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
            return title or url, markdown.strip(), {"visible_text_characters": len(markdown), "link_count": 0, "heading_count": 0, "table_count": 0, "table_rows": 0}
    except Exception as exc:
        print(f"Crawl4AI fallback for {url}: {exc}")
    return None


def _request_get(url: str) -> requests.Response:
    try:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    except requests.exceptions.SSLError:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT, verify=False)
    response.raise_for_status()
    return response


def _crawl_with_requests(url: str) -> tuple[str, str, dict, str]:
    response = _request_get(url)
    content_type = response.headers.get("content-type", "")
    if "html" not in content_type.lower() and "text" not in content_type.lower():
        raise ValueError(f"Unsupported content type: {content_type}")
    title, markdown, stats = _html_to_markdown(response.text, url)
    if len(markdown) <= 150:
        raise ValueError(f"Extracted content too short from {url}")
    return title, markdown, stats, response.text


async def crawl_article(source: dict) -> dict:
    url = source["url"]
    html = ""
    crawled = None
    if not source.get("prefer_requests", True):
        crawled = await _crawl_with_crawl4ai(url)
    if crawled is None:
        title, markdown, stats, html = _crawl_with_requests(url)
    else:
        title, markdown, stats = crawled
    min_chars = 180 if source.get("allow_short") or source.get("page_type") == "document_pointer" else 500
    markdown = sanitize_crawled_markdown(markdown, url, source.get("title", ""), title, min_chars=min_chars)
    detected = detect_page_type(markdown, url, int(stats.get("link_count", 0)))
    page_type = source.get("page_type") or detected
    is_primary = bool(source.get("is_primary_evidence", page_type not in {"listing_page", "document_pointer"}))
    return {
        "url": url,
        "title": source.get("title") or title,
        "institution": source["institution"],
        "category": source["category"],
        "sub_category": source.get("sub_category", ""),
        "admission_year": source["admission_year"],
        "date_crawled": datetime.now().astimezone().isoformat(timespec="seconds"),
        "language": "vi" if ".vn" in urlparse(url).netloc else "en",
        "source_domain": urlparse(url).netloc,
        "page_type": page_type,
        "detected_page_type": detected,
        "is_primary_evidence": is_primary,
        "parent_url": source.get("parent_url", ""),
        "discovered_from": source.get("discovered_from", ""),
        "child_sources": discover_relevant_child_sources(html, url) if html else [],
        "crawl_stats": stats,
        "content_markdown": markdown,
    }


def _quality_status(record: dict) -> str:
    markdown = record.get("content_markdown", "")
    stats = record.get("crawl_stats", {}) or {}
    page_type = record.get("page_type") or detect_page_type(markdown, record.get("url", ""), int(stats.get("link_count", 0)))
    link_ratio = int(stats.get("link_count", 0)) / max(1, len(markdown) / 1000)
    if len(markdown) < 500:
        return "invalid"
    if page_type == "listing_page":
        return "listing_page_only"
    if page_type == "document_pointer":
        return "incomplete_detail"
    if page_type == "table_page" and int(stats.get("table_count", 0)) and int(stats.get("table_rows", 0)) <= 1:
        return "broken_table"
    if link_ratio > 8 and len(markdown) < 2500:
        return "incomplete_detail"
    return "complete" if len(markdown) >= 2500 else "usable_with_minor_noise"


def audit_news_files() -> list[dict]:
    report: list[dict] = []
    for path in sorted(DATA_DIR.glob("*.json")):
        try:
            record = __import__("json").loads(path.read_text(encoding="utf-8"))
        except Exception:
            report.append({"filename": path.name, "quality_status": "invalid"})
            continue
        markdown = record.get("content_markdown", "")
        markdown = "\n".join(line.replace("Ö", "Có") if "|" in line and "Ö" in line else line for line in markdown.splitlines())
        record["content_markdown"] = markdown
        stats = record.get("crawl_stats", {}) or {}
        link_count = int(stats.get("link_count", len(re.findall(r"\]\([^)]+\)|https?://", markdown))))
        visible_chars = int(stats.get("visible_text_characters", len(re.sub(r"\[[^\]]+\]\([^)]+\)", "", markdown))))
        page_type = record.get("page_type") or detect_page_type(markdown, record.get("url", ""), link_count)
        quality = record.get("data_quality") or _quality_status({**record, "page_type": page_type})
        record["page_type"] = page_type
        record["data_quality"] = quality
        if page_type in {"listing_page", "document_pointer"}:
            record["is_primary_evidence"] = False
        else:
            record["is_primary_evidence"] = bool(record.get("is_primary_evidence", True))
        path.write_text(__import__("json").dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report.append(
            {
                "filename": path.name,
                "source_url": record.get("url", ""),
                "page_type": page_type,
                "content_characters": len(markdown),
                "visible_text_characters": visible_chars,
                "number_of_links": link_count,
                "link_text_ratio": round(link_count / max(1, visible_chars / 1000), 4),
                "number_of_headings": int(stats.get("heading_count", len(re.findall(r"^#{1,6}\s+", markdown, flags=re.M)))),
                "number_of_tables": int(stats.get("table_count", len(re.findall(r"\|\s*---", markdown)))),
                "number_of_table_rows": int(stats.get("table_rows", len(re.findall(r"^\|", markdown, flags=re.M)))),
                "has_detail_evidence": bool(record.get("is_primary_evidence")) and page_type not in {"listing_page", "document_pointer"},
                "requires_child_source_crawl": page_type in {"listing_page", "document_pointer"},
                "quality_status": quality,
            }
        )
    write_json(QUALITY_REPORT_PATH, report)
    return report


async def crawl_all() -> list[dict]:
    setup_directory()
    saved: list[dict] = []
    for i, source in enumerate(ARTICLE_URLS, 1):
        try:
            article = await crawl_article(source)
            filename = safe_filename(f"{source['institution']}-{source['category']}-{source.get('sub_category', '')}-{source['admission_year']}.json")
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
    report = audit_news_files()
    print(f"Data quality report: {QUALITY_REPORT_PATH.relative_to(PROJECT_ROOT)} ({len(report)} records)")
    return saved


if __name__ == "__main__":
    asyncio.run(crawl_all())
