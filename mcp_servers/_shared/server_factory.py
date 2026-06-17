"""TOOLS 스펙 → FastMCP 서버 빌더.

@mcp.tool() 데코레이터가 시그니처/타입힌트/docstring 에서 스키마를 자동 생성한다
(§08 §5.2). 우리는 단일 소스(ToolSpec)에서 add_tool 로 동적 등록해, 같은 핸들러를
오케스트레이터(인프로세스)와 MCP 서버가 공유하도록 한다.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from mcp_servers._shared.tooling import ToolSpec


def build_server(
    name: str, tools: list[ToolSpec], *, host: str = "127.0.0.1", port: int = 8000
) -> FastMCP:
    mcp = FastMCP(name, host=host, port=port)
    for spec in tools:
        mcp.add_tool(spec.handler, name=spec.name, description=spec.description)
    return mcp
