"""공통 의존성 (§02 §3, §04 §2).

- 고객용: 요청에서 받은 company_id 를 검증해 Tenant 컨텍스트를 주입한다.
  (비회원 구조 — 인증 없음, §03 §1.2)
- 관리자용: Authorization 헤더의 Bearer 토큰을 검증한다.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, Query

from app.core.config import settings
from app.core.exceptions import InvalidRequest, Unauthorized
from app.tenancy import router as tenant_router
from app.tenancy.registry import Tenant


def require_tenant(company_id: str) -> Tenant:
    """company_id → Tenant. 유효하지 않으면 400 INVALID_REQUEST (§03 §1.2)."""
    tenant = tenant_router.resolve(company_id)
    if tenant is None:
        raise InvalidRequest(
            f"유효하지 않은 company_id 입니다: {company_id!r}",
            details={"company_id": company_id},
        )
    return tenant


def tenant_from_query(company_id: Annotated[str, Query(description="업체 식별자")]) -> Tenant:
    """GET 계열 의존성: 쿼리 파라미터 company_id (§03 §1.2)."""
    return require_tenant(company_id)


TenantFromQuery = Annotated[Tenant, Depends(tenant_from_query)]


def require_admin(
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """관리자 API 인증 (§03 §1.2). admin_token 미설정 시 항상 401."""
    if not settings.admin_token:
        raise Unauthorized("관리자 API 가 비활성화되어 있습니다(토큰 미설정).")
    expected = f"Bearer {settings.admin_token}"
    if authorization != expected:
        raise Unauthorized("유효하지 않은 관리자 토큰입니다.")


AdminAuth = Annotated[None, Depends(require_admin)]
