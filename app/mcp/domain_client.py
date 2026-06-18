"""도메인(일반) MCP 클라이언트 (§08 §6, A안 — 외부 업체별 서버).

오케스트레이터가 **외부 업체별 일반 서버**(general-pizza/chinese/chicken,
FastAPI+FastMCP)에 MCP 프로토콜로 도구를 호출한다. 서버 URL 은 테넌트
레지스트리(general_server_url)에서 온다. company_id 는 모든 호출에 강제 주입(격리).

도구 구현은 외부 프로젝트에 있으므로 인프로세스 폴백은 없다. 서버 미가동/오류 시
fail dict 를 반환하고, agent 노드가 답변 실패(§06 §10)로 처리한다.
"""
from __future__ import annotations

import asyncio
import json
import logging

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

logger = logging.getLogger("app.mcp.domain")

_CALL_TIMEOUT = 10.0


def _parse_result(call_result) -> dict:
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


async def call(server_url: str, name: str, company_id: str, **kwargs) -> dict:
    """외부 업체 일반 서버에 도구 호출. 미가동/오류 시 fail."""
    if not server_url:
        return {"success": False, "message": "일반 서버 URL 이 설정되지 않았습니다."}
    arguments = {"company_id": company_id, **kwargs}

    async def _call() -> dict:
        async with streamablehttp_client(server_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
                return _parse_result(result)

    try:
        return await asyncio.wait_for(_call(), timeout=_CALL_TIMEOUT)
    except Exception as e:
        logger.warning("일반 서버(%s) 도구 호출 실패: %s", server_url, e)
        return {"success": False, "message": "도구 서버에 연결할 수 없습니다."}
