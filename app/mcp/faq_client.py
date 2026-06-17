"""FAQ MCP 클라이언트 (§08 §3·§6, A안).

오케스트레이터가 **업체별 FAQ 서버 인스턴스**(streamable-http)에 MCP 프로토콜로
연결해 match_faq 를 호출한다. 서버 URL 은 테넌트 레지스트리(faq.server_url)에서 온다.

server_url 이 비었거나 서버에 연결할 수 없으면 인프로세스 matcher 로 폴백한다
(개발 편의 — 3개 서버를 안 띄워도 동작). 폴백 여부는 결과 used_remote 로 표기.
"""
from __future__ import annotations

import asyncio
import json
import logging

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from mcp_servers.faq_template import matcher

logger = logging.getLogger("app.mcp.faq")

_CONNECT_TIMEOUT = 5.0


def _parse_result(call_result) -> dict:
    """FastMCP CallToolResult → {matched, answer, score, question}."""
    sc = getattr(call_result, "structuredContent", None)
    if isinstance(sc, dict):
        # FastMCP 가 dict 반환을 {"result": {...}} 로 감쌀 수 있음
        if "matched" in sc:
            return sc
        if isinstance(sc.get("result"), dict):
            return sc["result"]
    # 텍스트 콘텐츠 폴백
    for block in getattr(call_result, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            try:
                data = json.loads(text)
                if isinstance(data, dict):
                    return data
            except json.JSONDecodeError:
                continue
    return {"matched": False}


async def _match_remote(server_url: str, question: str) -> dict:
    async def _call() -> dict:
        async with streamablehttp_client(server_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("match_faq", {"question": question})
                return _parse_result(result)

    return await asyncio.wait_for(_call(), timeout=_CONNECT_TIMEOUT)


async def match_faq(
    *, company_id: str, collection: str, threshold: float, server_url: str, question: str
) -> dict:
    """업체 FAQ 매칭. 원격 서버 우선, 실패 시 인프로세스 폴백."""
    if server_url:
        try:
            res = await _match_remote(server_url, question)
            res["used_remote"] = True
            return res
        except Exception as e:  # 연결 실패/타임아웃 → 폴백
            logger.warning("FAQ 원격 서버(%s) 연결 실패 → 인프로세스 폴백: %s", server_url, e)

    m = await matcher.match(
        question, collection=collection, company_id=company_id, threshold=threshold
    )
    return {
        "matched": m.matched,
        "answer": m.answer,
        "score": m.score,
        "question": m.question,
        "used_remote": False,
    }
