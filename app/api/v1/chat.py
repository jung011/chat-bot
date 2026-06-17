"""채팅 엔드포인트 (§03 §3.1~3.2). 비회원 — company_id 는 body 로 수신."""
from __future__ import annotations

import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

from app.api.deps import require_tenant
from app.api.http import envelope
from app.schemas.chat import ChatRequest, ChatSyncData
from app.services import chat_service

router = APIRouter()


@router.post("/chat")
async def chat(req: ChatRequest):
    """SSE 스트리밍 응답(meta/token/sources/done/error)."""
    tenant = require_tenant(req.company_id)

    async def event_source():
        async for ev in chat_service.chat_stream(
            tenant, session_id=req.session_id, message=req.message
        ):
            yield {"event": ev["event"], "data": json.dumps(ev["data"], ensure_ascii=False)}

    return EventSourceResponse(event_source())


@router.post("/chat/sync")
async def chat_sync(req: ChatRequest, request: Request):
    tenant = require_tenant(req.company_id)
    result = await chat_service.chat_sync(
        tenant, session_id=req.session_id, message=req.message
    )
    data = ChatSyncData(
        session_id=result.session_id,
        message_id=result.message_id,
        route=result.route,
        answer=result.answer,
        sources=result.sources,
        usage=result.usage,
    )
    return envelope(data.model_dump(), request)
