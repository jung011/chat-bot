"""라우팅 노드 (§06 §4.2) — Haiku.

질문을 chitchat/rag/agent 로 분류(계단형 필터 1단계 분기).
LLM 미설정/분류 실패 시 "rag" 기본값(검색 경로)으로 degrade.
"""
from __future__ import annotations

from app.core.exceptions import AppError
from app.llm.client import get_llm
from app.llm.models import Stage, model_for
from app.orchestration import prompts
from app.orchestration.state import RAGState

_VALID = {"chitchat", "rag", "agent"}


async def route(state: RAGState) -> dict:
    llm = get_llm()
    question = state.get("rewritten") or state["question"]
    if not llm.available:
        return {"route": "rag"}
    try:
        data = await llm.complete_json(
            system=prompts.ROUTE_SYSTEM, user=question, model=model_for(Stage.ROUTE)
        )
    except AppError:
        return {"route": "rag"}
    r = (data or {}).get("route")
    return {"route": r if r in _VALID else "rag"}
