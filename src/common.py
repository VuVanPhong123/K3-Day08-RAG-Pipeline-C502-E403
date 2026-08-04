"""Shared helpers for the University Admission RAG pipeline."""

from __future__ import annotations

import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


def configure_utf8() -> None:
    """Make Windows console output tolerant of Vietnamese text."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_filename(value: str, suffix: str | None = None) -> str:
    value = value.replace("Đ", "D").replace("đ", "d")
    text = unicodedata.normalize("NFKD", value)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-._").lower()
    text = re.sub(r"-{2,}", "-", text) or "document"
    if suffix and not text.endswith(suffix):
        text = f"{Path(text).stem}{suffix}"
    return text


def stable_hash(text: str, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def scalar_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool]:
    out: dict[str, str | int | float | bool] = {}
    for key, value in metadata.items():
        if value is None:
            out[key] = ""
        elif isinstance(value, (str, int, float, bool)):
            out[key] = value
        else:
            out[key] = json.dumps(value, ensure_ascii=False)
    return out


def tokenize(text: str) -> list[str]:
    """Unicode tokenizer that keeps Vietnamese accents, years, scores and codes."""
    pattern = r"(?u)[\wÀ-ỹ]+(?:[.-][\wÀ-ỹ]+)*"
    return [m.group(0).lower() for m in re.finditer(pattern, text)]


def first_sentences(text: str, max_chars: int = 900) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    parts = re.split(r"(?<=[.!?。])\s+", clean)
    selected: list[str] = []
    total = 0
    for part in parts:
        if not part:
            continue
        if total + len(part) > max_chars and selected:
            break
        selected.append(part)
        total += len(part)
    return " ".join(selected)[:max_chars].strip()
