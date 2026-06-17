"""세션 관리 엔드포인트 (§03 §3.4). 비회원 — session_id + company_id 로 조회/필터."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from app.api.deps import TenantFromQuery, require_tenant
from app.api.http import envelope
from app.core.exceptions import SessionNotFound
from app.db import repositories as repo
from app.schemas.chat import SessionCreateRequest

router = APIRouter()


def _iso(dt) -> str:
    return dt.isoformat() if dt else ""


@router.post("/sessions", status_code=201)
async def create_session(req: SessionCreateRequest, request: Request):
    tenant = require_tenant(req.company_id)
    s = await repo.create_session(tenant.company_id, req.title)
    return envelope({"session_id": s["session_id"], "created_at": _iso(s["created_at"])}, request)


@router.get("/sessions")
async def list_sessions(
    tenant: TenantFromQuery,
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    rows = await repo.list_sessions(tenant.company_id, limit=limit)
    data = [
        {"session_id": r["session_id"], "title": r["title"], "updated_at": _iso(r["updated_at"])}
        for r in rows
    ]
    return {"data": data, "next_cursor": None}


@router.get("/sessions/{session_id}/messages")
async def session_messages(session_id: str, tenant: TenantFromQuery):
    if await repo.get_session(session_id, tenant.company_id) is None:
        raise SessionNotFound("세션을 찾을 수 없습니다.")
    rows = await repo.list_messages(session_id, tenant.company_id)
    data = [
        {
            "message_id": r["message_id"], "role": r["role"], "content": r["content"],
            "route": r["route"], "created_at": _iso(r["created_at"]),
        }
        for r in rows
    ]
    return {"data": data, "next_cursor": None}


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, tenant: TenantFromQuery, request: Request):
    deleted = await repo.delete_session(session_id, tenant.company_id)
    if not deleted:
        raise SessionNotFound("세션을 찾을 수 없습니다.")
    return envelope({"deleted": True}, request)
