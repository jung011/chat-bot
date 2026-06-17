"""테넌트 라우터 (§01 §4.2, §03 §1.2).

비회원 구조: company_id 를 요청에서 직접 받는다. 라우팅은 **결정적**이며
(레지스트리 조회), 유효하지 않은 company_id 는 호출부에서 400 으로 처리한다.

파일럿은 단일 인프라(공용 Qdrant/Postgres)에 업체별 컬렉션/필터로 격리한다.
A안(업체별 FAQ 인스턴스 분리) 전환 시 Tenant.faq.vector_db 를 사용해
업체 인스턴스로 연결한다.
"""
from __future__ import annotations

from app.tenancy.registry import Tenant, get_registry


def resolve(company_id: str) -> Tenant | None:
    """company_id → Tenant. 없거나 비활성이면 None."""
    if not company_id:
        return None
    reg = get_registry()
    tenant = reg.get(company_id)
    if tenant is None or not tenant.active:
        return None
    return tenant


def is_valid(company_id: str) -> bool:
    return resolve(company_id) is not None
