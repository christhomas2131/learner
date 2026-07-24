"""Keyless web-search providers for candidate discovery.

Each provider degrades to [] on any failure (network, parse, rate-limit,
CAPTCHA, missing CLI) so discovery never breaks the request — a dead provider
just contributes nothing to the fused result. No paid API is ever called.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import re
from html import unescape
from typing import Protocol
from urllib.parse import parse_qs, quote, urlsplit

import httpx
from bs4 import BeautifulSoup

from app.core.config import settings
from app.core.logging import get_logger
from app.discovery.models import Candidate
from app.providers.claude_cli import _extract_json, claude_cli_available

log = get_logger("discovery")

# Wikipedia's API enforces its User-Agent policy — a descriptive UA with contact
# info; a generic bot UA gets 403. DuckDuckGo's HTML endpoint blocks non-browser
# UAs (returns a 202 challenge), so it needs a realistic browser UA + Accept.
_WIKI_UA = "Learner/1.0 (https://github.com/christhomas2131/learner; verified-learning tool)"
_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
)


class DiscoveryProvider(Protocol):
    name: str

    async def search(self, query: str, *, limit: int) -> list[Candidate]: ...


def _strip_html(text: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", text)).strip()


class WikipediaProvider:
    """MediaWiki search API (keyless). Encyclopedic / entity 'master data'."""

    name = "wikipedia"
    _API = "https://en.wikipedia.org/w/api.php"

    async def search(self, query: str, *, limit: int) -> list[Candidate]:
        params: dict[str, str | int] = {
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": max(1, limit), "srprop": "snippet",
        }
        try:
            async with httpx.AsyncClient(timeout=settings.AUTO_DISCOVERY_TIMEOUT_SECONDS,
                                         headers={"User-Agent": _WIKI_UA}) as client:
                resp = await client.get(self._API, params=params)
                resp.raise_for_status()
                data = resp.json()
        except Exception as e:  # noqa: BLE001 - degrade gracefully
            log.warning("wikipedia_failed", error=str(e))
            return []
        out: list[Candidate] = []
        for item in data.get("query", {}).get("search", []):
            title = item.get("title", "")
            if not title:
                continue
            url = "https://en.wikipedia.org/wiki/" + quote(title.replace(" ", "_"))
            out.append(Candidate(url=url, title=title,
                                 snippet=_strip_html(item.get("snippet", "")),
                                 providers=[self.name]))
        return out


class DuckDuckGoProvider:
    """DuckDuckGo HTML endpoint (keyless, unofficial). General web recall."""

    name = "duckduckgo"
    _URL = "https://html.duckduckgo.com/html/"

    async def search(self, query: str, *, limit: int) -> list[Candidate]:
        try:
            async with httpx.AsyncClient(timeout=settings.AUTO_DISCOVERY_TIMEOUT_SECONDS,
                                         headers={"User-Agent": _BROWSER_UA,
                                                  "Accept": "text/html",
                                                  "Accept-Language": "en-US,en;q=0.9"},
                                         follow_redirects=True) as client:
                resp = await client.post(self._URL, data={"q": query})
                resp.raise_for_status()
                html = resp.text
        except Exception as e:  # noqa: BLE001
            log.warning("duckduckgo_failed", error=str(e))
            return []
        return _parse_ddg(html, limit)


def _parse_ddg(html: str, limit: int) -> list[Candidate]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[Candidate] = []
    for result in soup.select("div.result"):
        link = result.select_one("a.result__a")
        if link is None:
            continue
        url = _ddg_unwrap(str(link.get("href", "")))
        if not url.startswith(("http://", "https://")):
            continue
        snippet_el = result.select_one(".result__snippet")
        out.append(Candidate(url=url, title=link.get_text(" ", strip=True),
                             snippet=snippet_el.get_text(" ", strip=True) if snippet_el else "",
                             providers=["duckduckgo"]))
        if len(out) >= limit:
            break
    return out


def _ddg_unwrap(href: str) -> str:
    """DDG result links are redirects: //duckduckgo.com/l/?uddg=<encoded>&rut=..."""
    if href.startswith("//"):
        href = "https:" + href
    try:
        parts = urlsplit(href)
    except ValueError:
        return href
    if "duckduckgo.com" in parts.netloc and parts.path.startswith("/l/"):
        target = parse_qs(parts.query).get("uddg")
        if target:
            return target[0]
    return href


class ClaudeWebProvider:
    """Discovery via the local `claude` CLI (subscription login, no API key).

    The model only *finds* candidate URLs; it never asserts an answer here. Bad
    or hallucinated URLs are self-correcting: confirm re-fetches server-side, so
    an unreachable URL is dropped and a reachable one still goes through
    cite-or-abstain verification.
    """

    name = "claude_web"

    async def _invoke(self, prompt: str) -> str | None:
        if not claude_cli_available():
            return None
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude", "-p", "--output-format", "json",
                "--allowedTools", "WebSearch,WebFetch",
                stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except OSError as e:
            log.warning("claude_web_failed", error=str(e))
            return None
        try:
            out, _err = await asyncio.wait_for(
                proc.communicate(prompt.encode()),
                timeout=settings.AUTO_DISCOVERY_TIMEOUT_SECONDS,
            )
        except TimeoutError:
            with contextlib.suppress(ProcessLookupError):
                proc.kill()
            log.warning("claude_web_timeout")
            return None
        if proc.returncode != 0:
            return None
        try:
            envelope = json.loads(out.decode())
        except json.JSONDecodeError:
            return None
        if envelope.get("is_error"):
            return None
        result = envelope.get("result")
        return result if isinstance(result, str) else None

    async def search(self, query: str, *, limit: int) -> list[Candidate]:
        raw = await self._invoke(_discovery_prompt(query, limit))
        if not raw:
            return []
        try:
            data = json.loads(_extract_json(raw, array=True))
        except Exception:  # noqa: BLE001
            return []
        if not isinstance(data, list):
            return []
        out: list[Candidate] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not isinstance(url, str) or not url.startswith(("http://", "https://")):
                continue
            out.append(Candidate(url=url, title=str(item.get("title") or url),
                                 snippet=str(item.get("snippet") or ""),
                                 providers=[self.name]))
        return out[:limit]


def _discovery_prompt(query: str, limit: int) -> str:
    return (
        "You are a research source finder for a verified-learning tool. Find up "
        f"to {limit} authoritative, real, currently-reachable web pages that would "
        "help answer the question. Prefer primary, official, academic, or reputable "
        'reference sources. Return ONLY a JSON array of objects with keys "url", '
        '"title", "snippet" (a one-sentence summary). No prose, no markdown fences. '
        "Only include URLs you are confident exist.\n\n"
        f"Question: {query}"
    )


class FixtureDiscoveryProvider:
    """Deterministic, offline provider for e2e/tests only (gated by
    AUTO_DISCOVERY_FIXTURE). Returns canned candidates for a known query so the
    discovery UI can be exercised without the network; returns nothing for other
    queries, so an ordinary abstention still abstains."""

    name = "fixture"

    async def search(self, query: str, *, limit: int) -> list[Candidate]:
        if "lovelace" not in query.lower():
            return []
        canned = [
            Candidate(url="https://en.wikipedia.org/wiki/Ada_Lovelace", title="Ada Lovelace",
                      snippet="English mathematician, regarded as the first computer programmer.",
                      providers=[self.name]),
            Candidate(url="https://www.britannica.com/biography/Ada-Lovelace",
                      title="Ada Lovelace | Britannica", snippet="Biography of Ada Lovelace.",
                      providers=[self.name]),
        ]
        return canned[:limit]


def enabled_providers() -> list[DiscoveryProvider]:
    """The discovery providers switched on in settings (each keyless)."""
    if settings.AUTO_DISCOVERY_FIXTURE:  # e2e/tests: deterministic + offline
        return [FixtureDiscoveryProvider()]
    provs: list[DiscoveryProvider] = []
    if settings.AUTO_DISCOVERY_WIKIPEDIA:
        provs.append(WikipediaProvider())
    if settings.AUTO_DISCOVERY_DUCKDUCKGO:
        provs.append(DuckDuckGoProvider())
    if settings.AUTO_DISCOVERY_CLAUDE_WEB:
        provs.append(ClaudeWebProvider())
    return provs
