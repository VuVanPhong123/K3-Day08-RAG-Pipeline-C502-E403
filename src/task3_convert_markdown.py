"""Task 3 - Standardize landing documents into Markdown."""

from __future__ import annotations

import json
from pathlib import Path

from markitdown import MarkItDown

from .common import configure_utf8, read_json

configure_utf8()

LANDING_DIR = Path(__file__).resolve().parent.parent / "data" / "landing"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "data" / "standardized"
SUPPORTED_SUFFIXES = {".pdf", ".docx", ".doc", ".json", ".html", ".htm", ".md", ".txt"}


def _manifest_by_filename() -> dict[str, dict]:
    manifest = read_json(LANDING_DIR / "legal" / "sources.json", [])
    return {item.get("filename", ""): item for item in manifest if isinstance(item, dict)}


def _metadata_header(title: str, metadata: dict) -> str:
    fields = [
        ("Institution", metadata.get("institution", "")),
        ("Source", metadata.get("url", metadata.get("source", ""))),
        ("Admission year", metadata.get("admission_year", "")),
        ("Document type", metadata.get("document_type", metadata.get("category", ""))),
        ("Retrieved at", metadata.get("retrieved_at", metadata.get("date_crawled", ""))),
    ]
    lines = [f"# {title or metadata.get('title') or 'Tài liệu tuyển sinh'}", ""]
    for key, value in fields:
        if value != "":
            lines.append(f"- {key}: {value}")
    lines.extend(["", "---", ""])
    return "\n".join(lines)


def _convert_pdf_like(path: Path) -> str:
    try:
        result = MarkItDown().convert(str(path))
        text = getattr(result, "text_content", "") or ""
        if len(text.strip()) > 200:
            return text.strip()
    except Exception as exc:
        print(f"MarkItDown fallback for {path.name}: {exc}")

    try:
        import pdfplumber

        pages: list[str] = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(text.strip())
        return "\n\n".join(pages).strip()
    except Exception as exc:
        raise RuntimeError(f"Cannot convert {path.name}: {exc}") from exc


def _convert_json(path: Path) -> tuple[str, dict, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    title = data.get("title", path.stem)
    metadata = {
        "title": title,
        "url": data.get("url", ""),
        "institution": data.get("institution", ""),
        "category": data.get("category", "news"),
        "admission_year": data.get("admission_year", ""),
        "date_crawled": data.get("date_crawled", ""),
    }
    body = data.get("content_markdown") or data.get("content") or ""
    return title, metadata, body.strip()


def _convert_plain(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace").strip()


def convert_file(path: Path, manifest: dict[str, dict]) -> Path | None:
    rel = path.relative_to(LANDING_DIR)
    if path.name.startswith(".") or path.suffix.lower() not in SUPPORTED_SUFFIXES:
        return None
    if path.name == "sources.json":
        return None

    output_dir = OUTPUT_DIR / rel.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{path.stem}.md"
    metadata: dict = {}
    title = path.stem.replace("-", " ").title()

    if path.suffix.lower() == ".json":
        title, metadata, body = _convert_json(path)
    elif path.suffix.lower() in {".pdf", ".docx", ".doc"}:
        metadata = manifest.get(path.name, {})
        title = metadata.get("title", title)
        body = _convert_pdf_like(path)
    else:
        body = _convert_plain(path)

    if len(body) <= 200:
        raise ValueError(f"Converted content too short: {path}")

    content = _metadata_header(title, metadata) + body + "\n"
    output_path.write_text(content, encoding="utf-8", newline="\n")
    return output_path


def convert_all() -> dict[str, int]:
    print("Task 3: Convert landing data to Markdown")
    manifest = _manifest_by_filename()
    success = 0
    failed = 0
    for path in sorted(LANDING_DIR.rglob("*")):
        if not path.is_file():
            continue
        try:
            output = convert_file(path, manifest)
            if output:
                success += 1
                print(f"OK {path.relative_to(LANDING_DIR)} -> {output.relative_to(OUTPUT_DIR)}")
        except Exception as exc:
            failed += 1
            print(f"ERROR {path.relative_to(LANDING_DIR)}: {exc}")

    print(f"Summary: {success} converted, {failed} failed")
    if success == 0:
        raise SystemExit(1)
    return {"success": success, "failed": failed}


if __name__ == "__main__":
    convert_all()
