"""Chunk extracted text into passages, preserving character offsets."""

from __future__ import annotations

import re
from dataclasses import dataclass

_PARA = re.compile(r"\n\s*\n")


@dataclass
class Chunk:
    text: str
    char_start: int
    char_end: int
    index: int


def chunk_text(text: str, target_chars: int = 800, max_chars: int = 1200) -> list[Chunk]:
    text = text.strip()
    if not text:
        return []

    chunks: list[Chunk] = []
    cursor = 0
    buf: list[str] = []
    buf_start = 0
    length = 0

    def flush(end: int) -> None:
        nonlocal buf, length
        if not buf:
            return
        chunk_str = "\n\n".join(buf).strip()
        if chunk_str:
            chunks.append(Chunk(chunk_str, buf_start, end, len(chunks)))
        buf = []
        length = 0

    # Split into paragraphs but keep offsets by walking the original text.
    for para in _split_with_offsets(text):
        ptext, pstart, pend = para
        if not buf:
            buf_start = pstart
        if length and length + len(ptext) > max_chars:
            flush(cursor)
            buf_start = pstart
        buf.append(ptext)
        length += len(ptext)
        cursor = pend
        if length >= target_chars:
            flush(pend)
    flush(cursor)
    return chunks


def _split_with_offsets(text: str) -> list[tuple[str, int, int]]:
    result: list[tuple[str, int, int]] = []
    pos = 0
    for match in _PARA.finditer(text):
        segment = text[pos : match.start()]
        if segment.strip():
            result.append((segment.strip(), pos, match.start()))
        pos = match.end()
    tail = text[pos:]
    if tail.strip():
        result.append((tail.strip(), pos, len(text)))
    return result or [(text.strip(), 0, len(text))]
