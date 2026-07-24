"""Session .docx export."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.core.enums import ClaimStatus, TopLevelStatus
from app.db.base import AsyncSessionLocal, new_uuid
from app.db.init_db import create_all, drop_all
from app.models import Session
from app.pipeline.engine import PipelineResult
from app.schemas.api import ClaimOut, EvidenceOut
from app.services.audit import persist_result
from app.services.export import export_session_docx
from app.services.user import get_or_create_demo_user


@pytest.fixture
async def fresh_db():
    await drop_all()
    await create_all()
    yield
    await drop_all()


async def test_export_session_docx(fresh_db):
    async with AsyncSessionLocal() as s:
        user = await get_or_create_demo_user(s)
        sess = Session(user_id=user.id, title="Study session")
        s.add(sess)
        await s.flush()
        quote = "Photosynthesis converts light energy into chemical energy."
        claim = ClaimOut(
            claim_id="claim-1", text=quote, material=True, status=ClaimStatus.SUPPORTED,
            citations=[],
            evidence=[EvidenceOut(source_id="s1", passage_id="p1", quotation=quote,
                                  retrieval_score=0.9)],
            verifier_explanation="ok",
        )
        result = PipelineResult(
            request_id=new_uuid(), session_id=sess.id, status=TopLevelStatus.VERIFIED,
            question="What is photosynthesis?", answer=f"{quote} [1]", claims=[claim],
            sources=[], attempts=1, duration_ms=1, completed_stages=[], provider="none",
            model_identifier=None, contradiction_detail=None,
            created_at=datetime.now(UTC), reasons=[],
        )
        await persist_result(s, user_id=user.id, result=result)

        filename, data = await export_session_docx(s, user, sess.id)
        assert filename.endswith(".docx")
        # A .docx is a zip — starts with the PK magic bytes.
        assert data[:2] == b"PK" and len(data) > 1000
