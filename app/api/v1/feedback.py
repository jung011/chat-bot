"""피드백 엔드포인트 (§03 §3.5)."""
from __future__ import annotations

from fastapi import APIRouter, Request

from app.api.deps import require_tenant
from app.api.http import envelope
from app.db import repositories as repo
from app.schemas.chat import FeedbackRequest

router = APIRouter()


@router.post("/messages/{message_id}/feedback")
async def feedback(message_id: str, req: FeedbackRequest, request: Request):
    tenant = require_tenant(req.company_id)
    await repo.add_feedback(
        message_id=message_id, company_id=tenant.company_id, rating=req.rating, reason=req.reason
    )
    return envelope({"recorded": True}, request)
