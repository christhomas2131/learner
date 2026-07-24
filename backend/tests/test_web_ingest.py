"""Web ingestion: SSRF guard (scheme + private IPs + per-redirect-hop) and a
byte-capped snapshot fetch. Mocked fetch/DNS — no real network."""

from __future__ import annotations

import pytest

from app.core.enums import SourceState, SourceType
from app.db.base import AsyncSessionLocal
from app.db.init_db import create_all, drop_all
from app.ingestion import web as web_mod
from app.ingestion.service import ingest_website
from app.ingestion.web import WebFetchError, _assert_public_url
from app.services.user import get_or_create_demo_user


@pytest.mark.parametrize(
    "url",
    ["file:///etc/passwd", "ftp://x/y", "http://127.0.0.1/x", "http://localhost/x",
     "http://192.168.1.1/x", "http://10.0.0.5/x", "http://[::1]/x"],
)
def test_ssrf_guard_blocks(url):
    with pytest.raises(WebFetchError):
        _assert_public_url(url)


@pytest.fixture
async def fresh_db():
    await drop_all()
    await create_all()
    yield
    await drop_all()


async def test_ingest_website_snapshot(monkeypatch, fresh_db):
    async def fake_fetch(url: str):
        return "Example Page", "Photosynthesis converts light energy into chemical energy."

    monkeypatch.setattr(web_mod, "fetch_and_extract", fake_fetch)

    async with AsyncSessionLocal() as s:
        user = await get_or_create_demo_user(s)
        src = await ingest_website(s, user_id=user.id, url="https://example.com/page")
        assert src.source_type == SourceType.APPROVED_WEBSITE
        assert src.state == SourceState.PENDING_APPROVAL
        assert src.url == "https://example.com/page"
        assert (src.structured_data or {}).get("kind") == "APPROVED_WEBSITE"


# --- Redirect-hop SSRF re-validation + streaming byte cap (fake httpx + DNS) ---


def _fake_getaddrinfo(host, *args, **kwargs):
    ip = {
        "public.test": "93.184.216.34",  # public
        "final.test": "93.184.216.34",   # public
        "evil.test": "10.0.0.1",         # RFC1918 private
    }.get(host, "93.184.216.34")
    return [(2, 1, 6, "", (ip, 0))]


class _FakeResp:
    def __init__(self, *, redirect_to=None, body=b"", ctype="text/html; charset=utf-8"):
        self._redirect_to = redirect_to
        self._body = body
        self.status_code = 302 if redirect_to else 200
        self.encoding = "utf-8"
        self.headers = {"location": redirect_to} if redirect_to else {"content-type": ctype}

    @property
    def is_redirect(self):
        return self._redirect_to is not None

    async def aiter_bytes(self):
        for i in range(0, len(self._body), 4096):  # chunked, to exercise the cap loop
            yield self._body[i:i + 4096]


class _FakeStreamCM:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self._resp

    async def __aexit__(self, *a):
        return False


class _FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)

    def stream(self, method, url):
        return _FakeStreamCM(self._responses.pop(0))

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False


def _install(monkeypatch, responses):
    monkeypatch.setattr(web_mod.socket, "getaddrinfo", _fake_getaddrinfo)
    monkeypatch.setattr(web_mod.httpx, "AsyncClient", lambda *a, **k: _FakeClient(responses))


async def test_rejects_ssrf_via_redirect(monkeypatch):
    # A public URL 302s to a private host — the per-hop guard must reject it.
    _install(monkeypatch, [_FakeResp(redirect_to="http://evil.test/metadata")])
    with pytest.raises(WebFetchError, match="non-public"):
        await web_mod.fetch_and_extract("http://public.test/start")


async def test_follows_public_redirect(monkeypatch):
    html = b"<html><title>T</title><body><main>Hello world, real content.</main></body></html>"
    _install(monkeypatch, [
        _FakeResp(redirect_to="http://final.test/page"),
        _FakeResp(body=html),
    ])
    _title, text = await web_mod.fetch_and_extract("http://public.test/start")
    assert "Hello world" in text


async def test_enforces_size_cap(monkeypatch):
    monkeypatch.setattr(web_mod, "MAX_BYTES", 1000)
    big = b"<html><body>" + b"x" * 5000 + b"</body></html>"
    _install(monkeypatch, [_FakeResp(body=big)])
    with pytest.raises(WebFetchError, match="too large"):
        await web_mod.fetch_and_extract("http://public.test/big")
