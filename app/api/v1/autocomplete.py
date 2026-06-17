"""자동완성 엔드포인트 (§03 §3.3). company_id 는 query 로 수신."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.api.deps import TenantFromQuery
from app.api.http import envelope
from app.services import autocomplete_service

router = APIRouter()


@router.get("/autocomplete")
async def autocomplete(
    tenant: TenantFromQuery,
    request: Request,
    q: Annotated[str, Query(description="입력 중 텍스트(prefix)")],
    limit: Annotated[int, Query(ge=1, le=20)] = 8,
):
    data = await autocomplete_service.autocomplete(tenant.company_id, q, limit=limit)
    return envelope(data.model_dump(), request)
