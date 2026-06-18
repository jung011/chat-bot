"""FAQ MCP 클라이언트 (§08 §3·§6, A안 — 외부 업체별 서버).

오케스트레이터가 **외부 업체별 FAQ 서버**(faq-pizza/chinese/chicken, FastAPI+FastMCP)에
MCP 프로토콜(streamable-http)로 연결해 match_faq 를 호출한다. 서버 URL 은 테넌트
레지스트리(faq.server_url)에서 온다.

원격 전용 — FAQ 매칭 로직(임베딩/임계값/컬렉션)은 **faq 서버가 소유**하므로 오케스트레이터는
재구현하지 않는다(domain_client 와 일관). 서버 미가동/오류 시 matched=False 로 통과시켜
다음 단계(rag)로 넘긴다.
"""
from __future__ import annotations

import asyncio
import json
import logging

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.core.config import settings

logger = logging.getLogger("app.mcp.faq")


def _parse_result(call_result) -> dict:
    sc = getattr(call_result, "structuredContent", None)
    if isinstance(sc, dict):
        if "matched" in sc:
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
    return {"matched": False}


async def match_faq(*, server_url: str, question: str) -> dict:
    """업체 FAQ 매칭(원격, 0단계 즉답). 서버 미가동/오류 시 {matched: False} 로 통과."""
    if not server_url:
        return {"matched": False}

    async def _call() -> dict:
        async with streamablehttp_client(server_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("match_faq", {"question": question})
                return _parse_result(result)

    try:
        return await asyncio.wait_for(_call(), timeout=settings.faq_call_timeout_seconds)
    except Exception as e:
        logger.warning("FAQ 외부 서버(%s) 연결 실패 → 통과(rag 로): %s", server_url, e)
        return {"matched": False}


async def search_faq(*, server_url: str, question: str, top_k: int = 5) -> list[dict]:
    """FAQ 후보 top-K(임계값 없음) — 복합/일반 질문의 생성 컨텍스트용. 실패 시 []."""
    if not server_url:
        return []

    async def _call() -> list[dict]:
        async with streamablehttp_client(server_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("search_faq", {"question": question, "top_k": top_k})
                data = _parse_result(result)
                return data.get("results", []) if isinstance(data, dict) else []

    try:
        return await asyncio.wait_for(_call(), timeout=settings.faq_call_timeout_seconds)
    except Exception as e:
        logger.warning("FAQ search 외부 서버(%s) 실패: %s", server_url, e)
        return []
