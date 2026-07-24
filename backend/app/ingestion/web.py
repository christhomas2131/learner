"""Approved-website ingestion: fetch a URL, extract readable text, snapshot it.

The answer pipeline only ever cites the stored snapshot, never live page content.
SSRF-guarded: http/https only, and the resolved host must be a public address
(no loopback/private/link-local) so a URL can't be used to probe internal hosts.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from app.core.logging import get_logger

log = get_logger("web_ingest")

MAX_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 5
_UA = "LearnerBot/0.1 (+personal verified-learning app)"


class WebFetchError(Exception):
    pass


def _assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise WebFetchError("Only http(s) URLs are allowed.")
    host = parsed.hostname
    if not host:
        raise WebFetchError("URL has no host.")
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError as e:
        raise WebFetchError(f"Could not resolve host: {e}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_loopback or ip.is_private or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise WebFetchError("Refusing to fetch a non-public address.")


def _extract(html: str) -> tuple[str, str]:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "template", "svg"]):
        tag.decompose()
    title = (soup.title.string.strip() if soup.title and soup.title.string else "").strip()
    # Prefer the main/article region if present.
    root = soup.find("main") or soup.find("article") or soup.body or soup
    text = root.get_text(separator="\n")
    lines = [ln.strip() for ln in text.splitlines()]
    cleaned = "\n\n".join(ln for ln in lines if ln)
    return title, cleaned


async def fetch_and_extract(url: str) -> tuple[str, str]:
    """Return (title, extracted_text). Raises WebFetchError on any problem.

    Redirects are followed manually so the SSRF guard runs on EVERY hop — a public
    URL must not be able to 30x-redirect into a loopback/private/metadata address.
    The body is streamed with a hard byte cap so an oversized page can't exhaust
    memory before we reject it.
    """
    current = httpx.URL(url)
    async with httpx.AsyncClient(
        timeout=15.0, follow_redirects=False, headers={"User-Agent": _UA}
    ) as client:
        for _ in range(MAX_REDIRECTS + 1):
            _assert_public_url(str(current))
            try:
                async with client.stream("GET", current) as resp:
                    if resp.is_redirect:
                        location = resp.headers.get("location")
                        if not location:
                            raise WebFetchError("Redirect without a Location header.")
                        current = current.join(location)
                        continue
                    if resp.status_code >= 400:
                        raise WebFetchError(f"Fetch returned HTTP {resp.status_code}.")
                    ctype = resp.headers.get("content-type", "")
                    if "html" not in ctype and "text" not in ctype:
                        raise WebFetchError(f"Unsupported content type: {ctype or 'unknown'}")
                    body = bytearray()
                    async for chunk in resp.aiter_bytes():
                        body += chunk
                        if len(body) > MAX_BYTES:
                            raise WebFetchError("Page is too large to ingest.")
                    title, text = _extract(
                        bytes(body).decode(resp.encoding or "utf-8", errors="replace")
                    )
                    if not text.strip():
                        raise WebFetchError("No readable text extracted from the page.")
                    return title or str(current), text
            except httpx.HTTPError as e:
                raise WebFetchError(f"Fetch failed: {e}") from e
    raise WebFetchError("Too many redirects.")
