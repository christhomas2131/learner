"""Security helpers: filename sanitization, hashing, MIME/extension checks."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

from app.core.enums import SourceType

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")

# extension -> (SourceType, allowed content-type prefixes)
EXTENSION_MAP: dict[str, SourceType] = {
    ".md": SourceType.CURATED_MARKDOWN,
    ".markdown": SourceType.CURATED_MARKDOWN,
    ".txt": SourceType.UPLOADED_TEXT,
    ".text": SourceType.UPLOADED_TEXT,
    ".pdf": SourceType.UPLOADED_PDF,
    ".docx": SourceType.UPLOADED_DOCX,
}


def sanitize_filename(name: str) -> str:
    name = unicodedata.normalize("NFKD", name)
    name = name.replace("\x00", "")
    base = Path(name).name  # strip any path components (defeats traversal)
    base = _SAFE.sub("_", base).strip("._") or "upload"
    return base[:200]


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_type_for_extension(filename: str) -> SourceType | None:
    return EXTENSION_MAP.get(Path(filename).suffix.lower())
