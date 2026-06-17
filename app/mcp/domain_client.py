"""도메인(일반) MCP 클라이언트 (§08 §6, A안 — 업체별 서버 분리).

오케스트레이터가 **업체별 일반 MCP 서버**(streamable-http)에 MCP 프로토콜로
도구를 호출한다. 서버 URL 은 테넌트 레지스트리(general_server_url)에서 온다.

server_url 이 비었거나 연결 불가하면 인프로세스 레지스트리(app/mcp/client)로 폴백한다.
company_id 는 모든 도구 호출에 강제 주입한다(테넌트 격리, §08 §6).
"""
from __future__ import annotations

import asyncio
import json
import logging

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.mcp import client as inproc

logger = logging.getLogger("app.mcp.domain")

_CALL_TIMEOUT = 10.0


def _parse_result(call_result) -> dict:
    """FastMCP CallToolResult → 도구 ok/fail dict."""
    sc = getattr(call_result, "structuredContent", None)
    if isinstance(sc, dict):
        if "success" in sc:
            return sc
        if isinstance(sc.get("result"), dict):
            return sc["result"]
    for block in getattr(call_result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                continue
    return {"success": False, "message": "도구 응답을 해석할 수 없습니다."}


async def _call_remote(server_url: str, name: str, arguments: dict) -> dict:
    async def _call() -> dict:
        async with streamablehttp_client(server_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
                return _parse_result(result)

    return await asyncio.wait_for(_call(), timeout=_CALL_TIMEOUT)


async def call(server_url: str, name: str, company_id: str, **kwargs) -> dict:
    """업체 일반 MCP 서버에 도구 호출. 원격 우선, 실패 시 인프로세스 폴백."""
    arguments = {"company_id": company_id, **kwargs}
    if server_url:
        try:
            return await _call_remote(server_url, name, arguments)
        except Exception as e:
            logger.warning("일반 MCP 서버(%s) 호출 실패 → 인프로세스 폴백: %s", server_url, e)
    return await inproc.call(name, company_id, **kwargs)
