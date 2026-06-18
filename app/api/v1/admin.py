"""관리자 엔드포인트 (§03 §3.6). 인증 필수(admin 토큰)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.api.deps import AdminAuth, require_tenant
from app.api.http import envelope
from app.services import admin_service

router = APIRouter()


class FaqItem(BaseModel):
    question: str
    answer: str
    category: str | None = None


class FaqUploadRequest(BaseModel):
    company_id: str
    items: list[FaqItem]


class IndexRequest(BaseModel):
    company_id: str
    source: str = "documents"
    scope: Literal["full", "incremental"] = "incremental"


@router.post("/admin/faq", status_code=202)
async def upload_faq(req: FaqUploadRequest, request: Request, _: AdminAuth):
    tenant = require_tenant(req.company_id)
    result = await admin_service.upload_faq(tenant, [i.model_dump() for i in req.items])
    return envelope(result, request)


@router.post("/admin/index", status_code=202)
async def trigger_index(req: IndexRequest, request: Request, _: AdminAuth):
    tenant = require_tenant(req.company_id)
    result = await admin_service.trigger_index(tenant, source=req.source, scope=req.scope)
    return envelope(result, request)


@router.post("/admin/registry/reload", status_code=200)
async def reload_registry(request: Request, _: AdminAuth):
    """`tenants.yaml` 핫리로드 — 무중단 신규 업체 반영(프로세스 재시작 불필요).

    레지스트리는 @lru_cache 라 평소 메모리 고정이지만, 이 엔드포인트로 캐시를 비우면
    다음 resolve 부터 갱신된 tenants.yaml 을 읽는다. 기존 업체 처리에 영향 없음.
    """
    from app.tenancy.registry import get_registry

    get_registry.cache_clear()
    reg = get_registry()  # 즉시 재구축(다음 요청 지연 방지)
    return envelope(
        {"reloaded": True, "tenants": [t.company_id for t in reg.all()]}, request
    )
