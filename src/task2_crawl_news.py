import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
import requests
from bs4 import BeautifulSoup

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DATA_DIR = Path(__file__).parent.parent / "data" / "landing" / "news"


def setup_directory():
    """Tạo thư mục data/landing/news/ nếu chưa có."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)


ARTICLE_URLS = [
    "https://diemthi.tuyensinh247.com/diem-chuan/dai-hoc-bach-khoa-ha-noi-BKA.html",
    "https://diemthi.tuyensinh247.com/diem-chuan/dai-hoc-kinh-te-quoc-dan-KHA.html",
    "https://diemthi.tuyensinh247.com/diem-chuan/dai-hoc-cong-nghe-dai-hoc-quoc-gia-ha-noi-QHI.html",
    "https://diemthi.tuyensinh247.com/diem-chuan/dai-hoc-ngoai-thuong-co-so-phia-bac-NTH.html",
    "https://diemthi.tuyensinh247.com/diem-chuan/hoc-vien-tai-chinh-HTC.html",
]


def extract_school_code(url: str) -> str:
    filename = url.split("/")[-1]
    return filename.replace(".html", "").split("-")[-1]


async def crawl_article(url: str) -> dict:
    """
    Crawl thông tin điểm chuẩn theo phương thức Điểm thi năm 2025 từ URL.

    Returns:
        {
            "url": str,
            "title": str,
            "section": str,
            "school_code": str,
            "date_crawled": str (ISO format),
            "content_markdown": str,
            "table_data": list[dict]
        }
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None, lambda: requests.get(url, headers=headers, timeout=15)
    )
    response.encoding = "utf-8"

    soup = BeautifulSoup(response.text, "html.parser")

    page_title = soup.title.string.strip() if soup.title else "Điểm chuẩn 2025"
    h1 = soup.find("h1")
    title = h1.text.strip() if h1 else page_title

    # Tìm phần Điểm chuẩn theo phương thức Điểm thi
    h3_target = None
    for h in soup.find_all(["h2", "h3", "h4"]):
        if "Điểm thi" in h.text:
            h3_target = h
            break

    section_title = (
        h3_target.text.strip()
        if h3_target
        else "Điểm chuẩn theo phương thức Điểm thi năm 2025"
    )

    table_rows_data = []
    markdown_lines = [f"# {title}", "", f"## {section_title}", ""]

    table = h3_target.find_next("table") if h3_target else soup.find("table")
    if table:
        rows = table.find_all("tr")
        header_cols = []
        for i, row in enumerate(rows):
            cols = [c.text.strip() for c in row.find_all(["th", "td"])]
            # Skip empty or promotional rows
            if not cols or any("Tuyensinh247" in c for c in cols):
                continue

            if not header_cols:
                header_cols = cols
                markdown_lines.append("| " + " | ".join(cols) + " |")
                markdown_lines.append(
                    "| " + " | ".join(["---"] * len(cols)) + " |"
                )
            else:
                if len(cols) == len(header_cols):
                    table_rows_data.append(dict(zip(header_cols, cols)))
                else:
                    table_rows_data.append({"raw_cols": cols})
                markdown_lines.append("| " + " | ".join(cols) + " |")

    content_markdown = "\n".join(markdown_lines)

    return {
        "url": url,
        "title": title,
        "section": section_title,
        "school_code": extract_school_code(url),
        "date_crawled": datetime.now().isoformat(),
        "content_markdown": content_markdown,
        "table_data": table_rows_data,
    }


async def crawl_all():
    """Crawl toàn bộ bài viết trong ARTICLE_URLS và lưu thành các file JSON."""
    setup_directory()

    all_articles = []

    for i, url in enumerate(ARTICLE_URLS, 1):
        print(f"[{i}/{len(ARTICLE_URLS)}] Crawling: {url}")
        article = await crawl_article(url)
        all_articles.append(article)

        # Lưu từng file JSON cho từng trường
        filename = f"article_{i:02d}.json"
        filepath = DATA_DIR / filename
        filepath.write_text(json.dumps(article, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  [OK] Saved: {filepath}")

    # Lưu 1 file tổng hợp duy nhất chứa toàn bộ dữ liệu 5 trường
    combined_filepath = DATA_DIR / "diem_chuan_diem_thi_2025_all.json"
    combined_filepath.write_text(
        json.dumps(all_articles, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  [OK] Saved combined file: {combined_filepath}")


if __name__ == "__main__":
    if not ARTICLE_URLS:
        print("⚠ Hãy điền ARTICLE_URLS trước khi chạy!")
    else:
        asyncio.run(crawl_all())


