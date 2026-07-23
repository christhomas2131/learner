"""Text extraction for supported source types."""

from __future__ import annotations

import io

from app.core.enums import SourceType


class ExtractionError(Exception):
    pass


def extract_text(data: bytes, source_type: SourceType) -> str:
    if source_type in (SourceType.CURATED_MARKDOWN, SourceType.UPLOADED_TEXT):
        return _decode(data)
    if source_type == SourceType.UPLOADED_PDF:
        return _extract_pdf(data)
    if source_type == SourceType.UPLOADED_DOCX:
        return _extract_docx(data)
    raise ExtractionError(f"Unsupported source type for extraction: {source_type}")


def _decode(data: bytes) -> str:
    for enc in ("utf-8", "utf-16", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    raise ExtractionError("Could not decode text content.")


def _extract_pdf(data: bytes) -> str:
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as e:  # noqa: BLE001
        raise ExtractionError(f"Invalid PDF: {e}") from e
    parts = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            parts.append(text)
    return "\n\n".join(parts)


def _extract_docx(data: bytes) -> str:
    import docx

    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as e:  # noqa: BLE001
        raise ExtractionError(f"Invalid DOCX: {e}") from e
    paras = [p.text for p in document.paragraphs if p.text.strip()]
    return "\n\n".join(paras)
