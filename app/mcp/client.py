"""MCP 클라이언트 (§02 §4, §08 §6).

오케스트레이터가 도메인 도구를 호출하는 진입점이다.

파일럿 구현: 모든 도메인 TOOLS 를 인프로세스 레지스트리로 모아 직접 호출한다
(테스트/실행 용이, §08 §8 통신방식 미결정). 운영 전환 시 이 클라이언트를
표준 MCP 프로토콜(stdio/HTTP) 호출로 교체하면 호출부(orchestration)는 그대로다.

규칙(§08 §6):
- company_id 는 오케스트레이터가 주입 → 모든 도구 호출에 필수.
- 멱등(읽기전용) 도구만 재시도(본 파일럿 도구는 전부 읽기전용).
- 에러는 표준 형태로 변환하지 않고 도구의 ok/fail dict 를 그대로 전달한다.
"""
from __future__ import annotations

from functools import lru_cache

from mcp_servers._shared.responses import fail
from mcp_servers._shared.tooling import ToolSpec
from mcp_servers.domains.documents.tools import TOOLS as DOC_TOOLS
from mcp_servers.domains.order.tools import TOOLS as ORDER_TOOLS
from mcp_servers.domains.store.tools import TOOLS as STORE_TOOLS

_ALL: list[ToolSpec] = [*DOC_TOOLS, *STORE_TOOLS, *ORDER_TOOLS]


@lru_cache
def _registry() -> dict[str, ToolSpec]:
    return {spec.name: spec for spec in _ALL}


def all_specs() -> list[ToolSpec]:
    """전체 도구 스펙(Tool RAG 인덱싱·테스트용)."""
    return list(_ALL)


def catalog() -> list[dict]:
    """tools 컬렉션 적재용 카탈로그."""
    return [spec.to_catalog() for spec in _ALL]


def has_tool(name: str) -> bool:
    return name in _registry()


async def call(name: str, company_id: str, **kwargs) -> dict:
    """도구 1개 호출. company_id 를 강제 주입한다(테넌트 격리)."""
    spec = _registry().get(name)
    if spec is None:
        return fail(f"요청한 도구를 찾을 수 없습니다: {name}")
    try:
        return await spec.handler(company_id=company_id, **kwargs)
    except TypeError as e:
        # 모델이 잘못된 인자를 준 경우(§08 §5.2 인자 검증)
        return fail(f"도구 인자가 올바르지 않습니다: {e}")
