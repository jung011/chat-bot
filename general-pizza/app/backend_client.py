"""업체 백엔드 API 클라이언트 (HTTP).

정형/실시간 서비스 데이터(메뉴·가격·매장·배달·주문)는 업체 백엔드 API 를 호출해
가져온다. DB 직접 접근 대신 API 를 타서 비즈니스 로직·검증·권한을 재사용한다.
(MCP 도구는 이 클라이언트를 감싸는 얇은 어댑터일 뿐 — 데이터 소유는 백엔드)
"""
from __future__ import annotations

import httpx

from app.config import settings

_TIMEOUT = settings.backend_timeout_seconds


async def get(path: str, params: dict | None = None) -> dict | None:
    """백엔드 GET. 실패 시 None(도구가 fail 처리)."""
    url = f"{settings.backend_url}{path}"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            r = await client.get(url, params=params or {})
            r.raise_for_status()
            return r.json()
    except Exception:
        return None
