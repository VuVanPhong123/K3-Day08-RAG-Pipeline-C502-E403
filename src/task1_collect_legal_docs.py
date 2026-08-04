"""Task 1 - Collect official university admission documents.

The lab folder is named ``legal`` for historical reasons. In this project it
stores official PDF/DOCX admission documents: admission schemes, quotas,
tuition and scholarship documents.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Iterable

import requests

from .common import configure_utf8, now_iso, safe_filename, write_json

configure_utf8()

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "landing" / "legal"
MANIFEST_PATH = DATA_DIR / "sources.json"
MIN_FILE_SIZE = 1024
TIMEOUT = 30
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; UniversityAdmissionRAG/1.0; "
        "+https://example.local/student-project)"
    )
}

DOCUMENT_SOURCES = [
    {
        "filename": "vinuni-admission-scheme-2025.pdf",
        "title": "Đề án tuyển sinh đại học năm 2025 Trường Đại học VinUni",
        "url": "https://admissions.vinuni.edu.vn/wp-content/uploads/sites/6/2020/07/De-an-Tuyen-sinh-Dai-hoc-Nam-2025-Truong-Dai-hoc-VinUni.pdf",
        "institution": "VinUniversity",
        "document_type": "admission_scheme",
        "admission_year": 2025,
    },
    {
        "filename": "hcmus-admission-scheme-2025.pdf",
        "title": "Thông tin tuyển sinh 2025 Trường Đại học Khoa học tự nhiên, ĐHQG-HCM",
        "url": "https://tuyensinh.hcmus.edu.vn/wp-content/uploads/2025/06/THONG-TIN-TUYEN-SINH-2025-HCMUS_18062025.pdf",
        "institution": "Trường Đại học Khoa học tự nhiên, ĐHQG-HCM",
        "document_type": "admission_scheme",
        "admission_year": 2025,
    },
    {
        "filename": "hcmus-quota-methods-2025.pdf",
        "title": "Phụ lục chỉ tiêu và phương thức xét tuyển HCMUS năm 2025",
        "url": "https://tuyensinh.hcmus.edu.vn/wp-content/uploads/2025/06/Phu-luc-2.6-Chi-tieu-va-phuong-thuc-xet-tuyen-1.pdf",
        "institution": "Trường Đại học Khoa học tự nhiên, ĐHQG-HCM",
        "document_type": "admission_quota",
        "admission_year": 2025,
    },
    {
        "filename": "rmit-international-student-guide-2026.pdf",
        "title": "RMIT Vietnam International Student Guide 2026",
        "url": "https://www.rmit.edu.vn/assets/vn/en/assets-for-production/documents/pdfs/study-at-rmit/international-students/international-student-guide-2026.pdf",
        "institution": "RMIT Việt Nam",
        "document_type": "admission_guide",
        "admission_year": 2026,
    },
]


def setup_directory() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def _validate_content_type(url: str, content_type: str, filename: str) -> None:
    suffix = Path(filename).suffix.lower()
    guessed = mimetypes.guess_type(filename)[0] or ""
    allowed = {
        ".pdf": ("application/pdf",),
        ".docx": (
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/octet-stream",
        ),
        ".doc": ("application/msword", "application/octet-stream"),
    }
    if suffix not in allowed:
        raise ValueError(f"Unsupported extension for {filename}")
    if content_type and not any(kind in content_type for kind in allowed[suffix]):
        if "octet-stream" not in content_type and guessed not in content_type:
            raise ValueError(f"Unexpected content type for {url}: {content_type}")


def download_file(source: dict) -> dict:
    setup_directory()
    filename = safe_filename(source["filename"], Path(source["filename"]).suffix.lower())
    target = DATA_DIR / filename

    manifest_item = {**source, "filename": filename, "retrieved_at": now_iso()}
    if target.exists() and target.stat().st_size > MIN_FILE_SIZE:
        manifest_item["status"] = "exists"
        return manifest_item

    response = requests.get(source["url"], headers=HEADERS, timeout=TIMEOUT)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").split(";")[0].lower()
    _validate_content_type(source["url"], content_type, filename)

    content = response.content
    if len(content) <= MIN_FILE_SIZE:
        raise ValueError(f"Downloaded file too small: {filename} ({len(content)} bytes)")

    target.write_bytes(content)
    manifest_item["status"] = "downloaded"
    manifest_item["content_type"] = content_type
    manifest_item["size_bytes"] = len(content)
    return manifest_item


def collect_all(sources: Iterable[dict] = DOCUMENT_SOURCES) -> list[dict]:
    setup_directory()
    manifest: list[dict] = []
    errors: list[str] = []
    for source in sources:
        try:
            item = download_file(source)
            manifest.append(item)
            print(f"OK {item['filename']} ({item['status']})")
        except Exception as exc:
            message = f"{source.get('url', 'unknown')}: {exc}"
            errors.append(message)
            print(f"ERROR {message}")

    write_json(MANIFEST_PATH, manifest)
    if len([m for m in manifest if (DATA_DIR / m["filename"]).exists()]) < 3:
        raise RuntimeError("Task 1 requires at least 3 official PDF/DOC/DOCX files.")
    if errors:
        print("Some sources failed and were skipped:")
        for error in errors:
            print(f"- {error}")
    return manifest


if __name__ == "__main__":
    collect_all()
