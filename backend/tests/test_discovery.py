"""Auto source-discovery: fusion, providers (parsing + graceful degradation),
and the NEEDS_SOURCES -> confirm API flow. No real network anywhere — every
provider / fetch is mocked."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.enums import SourceState
from app.db.base import AsyncSessionLocal
from app.db.init_db import create_all, drop_all
from app.discovery import providers as providers_mod
from app.discovery import service as discovery_svc
from app.discovery.fusion import fuse_candidates, normalize_url
from app.discovery.models import Candidate
from app.main import app
from app.services.user import get_or_create_demo_user

BIO_TEXT = (
    "Photosynthesis converts light energy into chemical energy. "
    "It occurs in the chloroplasts of plant cells."
)


@pytest.fixture
async def client():
    await drop_all()
    await create_all()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    await drop_all()


# ----------------------------------------------------------------- fusion ----

def test_normalize_url_dedupes_trailing_slash_and_fragment():
    assert normalize_url("https://X.com/a/") == normalize_url("https://x.com/a#frag")


def test_fuse_dedupes_and_merges_providers():
    a = [Candidate(url="https://x.com/a", title="A", snippet="", providers=["wikipedia"]),
         Candidate(url="https://x.com/b", title="B", snippet="s", providers=["wikipedia"])]
    b = [Candidate(url="https://x.com/a/", title="A2", snippet="sa", providers=["duckduckgo"])]
    fused = fuse_candidates([a, b], k=60, limit=10)
    assert len(fused) == 2
    merged = next(c for c in fused if c.url.rstrip("/").endswith("/a"))
    assert set(merged.providers) == {"wikipedia", "duckduckgo"}
    assert merged.snippet == "sa"  # backfilled from the non-empty duplicate
    assert fused[0] is merged  # two providers -> higher RRF -> ranked first


def test_fuse_respects_limit():
    lst = [Candidate(url=f"https://x.com/{i}", title=str(i), providers=["wikipedia"])
           for i in range(20)]
    assert len(fuse_candidates([lst], k=60, limit=5)) == 5


# ------------------------------------------------- providers: parsing/degrade -

class _Resp:
    def __init__(self, *, json_data=None, text=""):
        self._json = json_data
        self.text = text

    def json(self):
        return self._json

    def raise_for_status(self):
        return None


def _fake_httpx(monkeypatch, *, json_data=None, text="", exc=None):
    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, *a, **k):
            if exc:
                raise exc
            return _Resp(json_data=json_data, text=text)

        async def post(self, *a, **k):
            if exc:
                raise exc
            return _Resp(json_data=json_data, text=text)

    monkeypatch.setattr(providers_mod.httpx, "AsyncClient", _Client)


async def test_wikipedia_parses(monkeypatch):
    payload = {"query": {"search": [
        {"title": "Photosynthesis", "snippet": "light <span>energy</span>"},
        {"title": "Cellular respiration", "snippet": "glucose"},
    ]}}
    _fake_httpx(monkeypatch, json_data=payload)
    out = await providers_mod.WikipediaProvider().search("photosynthesis", limit=5)
    assert [c.title for c in out] == ["Photosynthesis", "Cellular respiration"]
    assert out[0].url == "https://en.wikipedia.org/wiki/Photosynthesis"
    assert "<span>" not in out[0].snippet and "energy" in out[0].snippet
    assert out[0].providers == ["wikipedia"]


async def test_wikipedia_degrades_on_error(monkeypatch):
    _fake_httpx(monkeypatch, exc=RuntimeError("boom"))
    assert await providers_mod.WikipediaProvider().search("x", limit=5) == []


async def test_duckduckgo_parses_and_unwraps_redirect(monkeypatch):
    html = (
        '<div class="result"><a class="result__a" '
        'href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fbio&rut=x">'
        'Bio Page</a><a class="result__snippet">All about photosynthesis</a></div>'
    )
    _fake_httpx(monkeypatch, text=html)
    out = await providers_mod.DuckDuckGoProvider().search("photosynthesis", limit=5)
    assert out and out[0].url == "https://example.com/bio"
    assert out[0].title == "Bio Page"
    assert "photosynthesis" in out[0].snippet
    assert out[0].providers == ["duckduckgo"]


async def test_duckduckgo_degrades_on_error(monkeypatch):
    _fake_httpx(monkeypatch, exc=RuntimeError("captcha"))
    assert await providers_mod.DuckDuckGoProvider().search("x", limit=5) == []


async def test_claude_web_parses(monkeypatch):
    async def fake_invoke(self, prompt):
        return '[{"url":"https://nih.gov/p","title":"NIH","snippet":"s"}]'

    monkeypatch.setattr(providers_mod.ClaudeWebProvider, "_invoke", fake_invoke)
    out = await providers_mod.ClaudeWebProvider().search("q", limit=5)
    assert out and out[0].url == "https://nih.gov/p"
    assert out[0].providers == ["claude_web"]


async def test_claude_web_unavailable_returns_empty(monkeypatch):
    monkeypatch.setattr(providers_mod, "claude_cli_available", lambda: False)
    assert await providers_mod.ClaudeWebProvider().search("q", limit=5) == []


# ------------------------------------------------------- discover() orchestration

class _FakeProvider:
    def __init__(self, name, result):
        self.name = name
        self._result = result

    async def search(self, query, *, limit):
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


async def test_discover_fuses_and_tolerates_provider_failure(monkeypatch):
    good = _FakeProvider("wikipedia",
                         [Candidate(url="https://a.com", title="A", providers=["wikipedia"])])
    bad = _FakeProvider("duckduckgo", RuntimeError("down"))
    monkeypatch.setattr(discovery_svc, "enabled_providers", lambda: [good, bad])
    discovery_id, cands = await discovery_svc.discover("q", limit=8)
    assert discovery_id and len(cands) == 1 and cands[0].url == "https://a.com"


# ------------------------------------------------------------- API: NEEDS_SOURCES

async def test_answers_needs_sources_on_miss(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTO_DISCOVERY_ENABLED", True)

    async def fake_discover(question, *, limit=None):
        return "disc-1", [Candidate(url="https://example.com/bio", title="Bio",
                                    snippet="photosynthesis", providers=["wikipedia", "duckduckgo"])]

    monkeypatch.setattr("app.api.v1.answers.discover", fake_discover)
    r = await client.post("/api/v1/answers", json={"question": "What is photosynthesis?"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "NEEDS_SOURCES"
    assert body["discovery_id"] == "disc-1"
    assert body["candidates"][0]["url"] == "https://example.com/bio"
    assert set(body["candidates"][0]["providers"]) == {"wikipedia", "duckduckgo"}


async def test_answers_no_discovery_when_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTO_DISCOVERY_ENABLED", False)
    r = await client.post("/api/v1/answers", json={"question": "What is photosynthesis?"})
    assert r.json()["status"] == "INSUFFICIENT_EVIDENCE"


async def test_answers_skip_discovery_flag(client, monkeypatch):
    monkeypatch.setattr(settings, "AUTO_DISCOVERY_ENABLED", True)
    r = await client.post("/api/v1/answers",
                          json={"question": "What is photosynthesis?", "skip_discovery": True})
    assert r.json()["status"] == "INSUFFICIENT_EVIDENCE"


async def test_discovery_confirm_ingests_and_answers(client, monkeypatch):
    from app.ingestion import web as web_mod

    async def fake_fetch(url):
        return "Bio Page", BIO_TEXT

    monkeypatch.setattr(web_mod, "fetch_and_extract", fake_fetch)
    r = await client.post("/api/v1/discovery/confirm", json={
        "question": "What is photosynthesis?",
        "discovery_id": "disc-1",
        "sources": [{"url": "https://example.com/bio", "title": "Bio"}],
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "VERIFIED"
    assert body["claims"] and body["audit_id"]

    # The confirmed source is now approved + retrievable.
    async with AsyncSessionLocal() as s:
        user = await get_or_create_demo_user(s)
        from sqlalchemy import select

        from app.models import Source
        src = (await s.execute(select(Source).where(Source.user_id == user.id))).scalars().first()
        assert src is not None and src.state == SourceState.APPROVED


async def test_discovery_confirm_rejects_private_url(client):
    r = await client.post("/api/v1/discovery/confirm", json={
        "question": "What is photosynthesis?",
        "sources": [{"url": "http://127.0.0.1/x"}],
    })
    assert r.status_code == 422  # SSRF guard -> IngestionError -> 0 approved -> ValidationError
