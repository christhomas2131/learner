"""Web ingestion: SSRF guard + snapshot ingestion (mocked fetch, no network)."""

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
