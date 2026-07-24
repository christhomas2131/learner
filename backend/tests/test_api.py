"""HTTP API tests against the ASGI app (httpx ASGITransport, no network)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.enums import SourceState
from app.db.base import AsyncSessionLocal
from app.db.init_db import create_all, drop_all
from app.ingestion.service import ingest_file, set_source_state
from app.main import app
from app.services.user import get_or_create_demo_user

BIO = (
    b"# Biology\n\nPhotosynthesis converts light energy into chemical energy. "
    b"It occurs in the chloroplasts of plant cells.\n"
)


@pytest.fixture(autouse=True)
async def fresh_db():
    await drop_all()
    await create_all()
    yield
    await drop_all()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _seed_bio_source(approved: bool = True) -> str:
    async with AsyncSessionLocal() as s:
        user = await get_or_create_demo_user(s)
        src = await ingest_file(s, user_id=user.id, filename="bio.md", data=BIO,
                                title="Biology", save_file=False)
        if approved:
            await set_source_state(s, src, SourceState.APPROVED)
        return src.id


async def test_health(client):
    r = await client.get("/api/v1/health")
    assert r.status_code == 200 and r.json()["status"] == "ok"


async def test_ready(client):
    r = await client.get("/api/v1/ready")
    assert r.status_code == 200 and r.json()["database"] is True


async def test_grounded_answer_verified(client):
    await _seed_bio_source()
    r = await client.post("/api/v1/answers", json={"question": "What is photosynthesis?"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "VERIFIED"
    assert body["claims"] and body["audit_id"]
    assert "VALIDATE_INPUT" in body["pipeline"]["completed_stages"]


async def test_grounded_answer_abstains(client):
    await _seed_bio_source()
    r = await client.post("/api/v1/answers", json={"question": "Who won the 2050 World Cup?"})
    assert r.status_code == 200
    assert r.json()["status"] == "INSUFFICIENT_EVIDENCE"


async def test_validation_error_on_empty_question(client):
    r = await client.post("/api/v1/answers", json={"question": ""})
    assert r.status_code == 422


async def test_session_crud(client):
    r = await client.post("/api/v1/sessions", json={"title": "My session"})
    assert r.status_code == 201
    sid = r.json()["id"]

    r = await client.get(f"/api/v1/sessions/{sid}")
    assert r.status_code == 200 and r.json()["title"] == "My session"

    r = await client.patch(f"/api/v1/sessions/{sid}", json={"saved": True})
    assert r.json()["saved"] is True

    r = await client.get("/api/v1/sessions")
    assert r.json()["total"] >= 1

    r = await client.delete(f"/api/v1/sessions/{sid}")
    assert r.status_code == 204
    r = await client.get(f"/api/v1/sessions/{sid}")
    assert r.status_code == 404


async def test_source_approval_workflow(client):
    sid = await _seed_bio_source(approved=False)
    r = await client.get(f"/api/v1/sources/{sid}")
    assert r.json()["state"] == "PENDING_APPROVAL"

    r = await client.post(f"/api/v1/sources/{sid}/approve")
    assert r.json()["state"] == "APPROVED"

    r = await client.get("/api/v1/sources")
    assert r.json()["total"] >= 1


async def test_subjects(client):
    r = await client.post("/api/v1/subjects", json={"name": "Chemistry"})
    assert r.status_code == 201
    r = await client.get("/api/v1/subjects")
    assert any(s["name"] == "Chemistry" for s in r.json())


async def test_analytics_shape(client):
    r = await client.get("/api/v1/analytics")
    assert r.status_code == 200
    assert "verified_rate" in r.json()


async def test_premium_enqueues(client):
    await _seed_bio_source()
    r = await client.post("/api/v1/answers",
                          json={"question": "Explain photosynthesis in depth", "mode": "premium"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "PENDING" and body["queue_id"]

    r = await client.get("/api/v1/queue", params={"status": "PENDING"})
    assert r.json()["total"] == 1


async def test_sse_stream_premium_enqueues(client):
    await _seed_bio_source()
    events: list[str] = []
    payload = None
    async with client.stream("POST", "/api/v1/answers/stream",
                             json={"question": "Explain photosynthesis", "mode": "premium"}) as resp:
        assert resp.status_code == 200
        current = None
        async for line in resp.aiter_lines():
            if line.startswith("event:"):
                current = line.split(":", 1)[1].strip()
                events.append(current)
            elif line.startswith("data:") and current == "queued":
                import json
                payload = json.loads(line.split(":", 1)[1].strip())
    assert "failed" not in events
    assert "queued" in events
    assert payload and payload["status"] == "PENDING" and payload["queue_id"]


async def test_sse_stream_order_and_final(client):
    await _seed_bio_source()
    events: list[str] = []
    final_payload = None
    async with client.stream("POST", "/api/v1/answers/stream",
                             json={"question": "What is photosynthesis?"}) as resp:
        assert resp.status_code == 200
        current_event = None
        async for line in resp.aiter_lines():
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
                events.append(current_event)
            elif line.startswith("data:") and current_event == "completed":
                import json
                final_payload = json.loads(line.split(":", 1)[1].strip())

    assert "request_started" in events
    assert "pipeline_stage" in events
    assert events[-1] == "completed"
    assert final_payload and final_payload["status"] == "VERIFIED"


async def test_worker_status_endpoint(client):
    r = await client.get("/api/v1/worker/status")
    assert r.status_code == 200
    body = r.json()
    assert "online" in body and "last_seen" in body


async def test_website_endpoint(client, monkeypatch):
    from app.ingestion import web as web_mod

    async def fake_fetch(url: str):
        return "Example Biology Page", "Photosynthesis converts light energy into chemical energy."

    monkeypatch.setattr(web_mod, "fetch_and_extract", fake_fetch)
    r = await client.post("/api/v1/sources/website", json={"url": "https://example.com/bio"})
    assert r.status_code == 201
    body = r.json()
    assert body["source_type"] == "APPROVED_WEBSITE"
    assert body["state"] == "PENDING_APPROVAL"
    assert body["url"] == "https://example.com/bio"


async def test_website_endpoint_rejects_private_url(client):
    r = await client.post("/api/v1/sources/website", json={"url": "http://127.0.0.1/x"})
    assert r.status_code == 422  # SSRF guard -> ValidationError


async def test_session_export_docx(client):
    await _seed_bio_source()
    ans = await client.post("/api/v1/answers", json={"question": "What is photosynthesis?"})
    sid = ans.json()["session_id"]
    r = await client.get(f"/api/v1/sessions/{sid}/export.docx")
    assert r.status_code == 200
    assert "wordprocessingml" in r.headers.get("content-type", "")
    assert r.content[:2] == b"PK"  # docx is a zip
