"""도구 스펙 (단일 소스).

각 도메인은 `TOOLS: list[ToolSpec]` 를 노출한다. 이 스펙 하나로
1) FastMCP 서버 등록(server.py), 2) 오케스트레이터 인프로세스 호출(app/mcp/client),
3) Tool RAG 인덱싱(scripts/seed_demo → tools 컬렉션) 을 모두 구동한다.

description/params_schema 는 §08 §4.4·§7 규칙을 따른다(Tool RAG 검색 품질 직결).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

# 도구 핸들러: company_id 등 인자를 받아 ok/fail dict 를 반환(비동기 통일)
Handler = Callable[..., Awaitable[dict]]


@dataclass(frozen=True)
class ToolSpec:
    server: str                 # 소속 MCP 서버(documents/store/order)
    name: str                   # 도구명(고유)
    description: str            # Tool RAG 인덱싱용 설명(§08 §7)
    params_schema: dict[str, Any]
    handler: Handler

    def to_catalog(self) -> dict:
        """tools 컬렉션 적재용 메타(§04 §3.2 tools payload)."""
        return {
            "server": self.server,
            "name": self.name,
            "description": self.description,
            "params_schema": self.params_schema,
        }
