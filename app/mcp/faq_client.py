"""FAQ MCP 클라이언트 (§08 §3·§6, A안).

오케스트레이터가 **외부 업체별 FAQ 서버**(faq-pizza/chinese/chicken, FastAPI+FastMCP)에
MCP 프로토콜(streamable-http)로 연결해 match_faq 를 호출한다. 서버 URL 은 테넌트
레지스트리(faq.server_url)에서 온다.

서버 연결 실패 시, 오케스트레이터 자체 retrieval 로 폴백한다(외부 서버와 동일한 공유
Qdrant `faq_<id>` 컬렉션을 직접 조회). 폴백 여부는 used_remote 로 표기.
"""
from __future__ import annotations

import asyncio
import json
import logging

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.retrieval import vector_store

logger = logging.getLogger("app.mcp.faq")

_CONNECT_TIMEOUT = 5.0


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


async def _match_remote(server_url: str, question: str) -> dict:
    async def _call() -> dict:
        async with streamablehttp_client(server_url) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("match_faq", {"question": question})
                return _parse_result(result)

    return await asyncio.wait_for(_call(), timeout=_CONNECT_TIMEOUT)


async def _match_local(collection: str, company_id: str, threshold: float, question: str) -> dict:
    """폴백 — 오케스트레이터 자체 retrieval 로 공유 Qdrant 직접 조회."""
    hits = await vector_store.search(
        collection, question, company_id=company_id, top_k=1, score_threshold=threshold
    )
    if not hits:
        return {"matched": False, "score": 0.0, "used_remote": False}
    top = hits[0]
    return {
        "matched": True,
        "answer": top.payload.get("answer"),
        "question": top.payload.get("question"),
        "score": round(top.score, 4),
        "used_remote": False,
    }


async def match_faq(
    *, company_id: str, collection: str, threshold: float, server_url: str, question: str
) -> dict:
    """업체 FAQ 매칭. 외부 서버 우선, 실패 시 자체 retrieval 폴백."""
    if server_url:
        try:
            res = await _match_remote(server_url, question)
            res["used_remote"] = True
            return res
        except Exception as e:
            logger.warning("FAQ 외부 서버(%s) 연결 실패 → 자체 retrieval 폴백: %s", server_url, e)
    return await _match_local(collection, company_id, threshold, question)
