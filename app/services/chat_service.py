"""채팅 서비스 (§03 §3.1~3.2, §06).

계단형 필터 오케스트레이션을 호출하고, 세션/메시지 영속화·로깅·폴백을 처리한다.
- chat_sync: 한 번에 답변(비스트리밍).
- chat_stream: SSE 이벤트 제너레이터(meta→token*→sources→done|error).
두 경로 모두 동일한 plan 그래프 결과를 공유한다(§02 graph.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator

from app.autocomplete import suggester
from app.core.config import settings
from app.core.exceptions import LLMTimeout, SessionNotFound
from app.db import repositories as repo
from app.llm.client import get_llm
from app.llm.models import Stage, model_for
from app.memory import short_term
from app.orchestration import prompts
from app.orchestration.graph import run_plan
from app.orchestration.nodes import generate as gen_node
from app.orchestration.nodes import verify as verify_node
from app.orchestration.state import initial_state
from app.tenancy.registry import Tenant


@dataclass
class ChatResult:
    session_id: str
    message_id: str
    route: str
    answer: str
    sources: list[dict] = field(default_factory=list)
    usage: dict = field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0})


async def _ensure_session(tenant: Tenant, session_id: str | None) -> str:
    if session_id:
        s = await repo.get_session(session_id, tenant.company_id)
        if s is None:
            # 세션의 company_id 가 다르거나 없음 → 노출 최소화(§03 §3.4)
            raise SessionNotFound("세션을 찾을 수 없습니다.")
        return session_id
    created = await repo.create_session(tenant.company_id)
    return created["session_id"]


def _mk_state(tenant: Tenant, question: str, history: list[dict]):
    return initial_state(
        company_id=tenant.company_id,
        question=question,
        history=history,
        persona=tenant.persona,
        business_info=tenant.business_info_text(),
        faq_collection=tenant.faq.collection,
        faq_threshold=tenant.faq.threshold,
        faq_server_url=tenant.faq.server_url,
        general_server_url=tenant.general_server_url,
        doc_top_k=tenant.retrieval.doc_top_k,
        doc_top_n=tenant.retrieval.doc_top_n,
        tool_top_k=tenant.retrieval.tool_top_k,
    )


async def _failure_message(tenant: Tenant, question: str) -> str:
    """답변 실패(A·C) 폴백 — 추천 질문 + 매장 연락처(§06 §10.3)."""
    recs = await suggester.recommend(tenant.company_id, question, n=3)
    phone = tenant.business_info.get("phone", "")
    if recs:
        bullets = "\n".join(f"• {r}" for r in recs)
        return prompts.FALLBACK["fail_with_suggestions"].format(suggestions=bullets, phone=phone)
    return prompts.FALLBACK["fail_no_suggestions"]


async def _persist(
    tenant: Tenant, session_id: str, question: str, result: ChatResult, matched: bool
) -> None:
    cid = tenant.company_id
    await repo.add_message(session_id=session_id, company_id=cid, role="user", content=question)
    await repo.add_message(
        session_id=session_id, company_id=cid, role="assistant", content=result.answer,
        route=result.route, sources=result.sources, usage=result.usage,
        message_id=result.message_id,
    )
    await short_term.append(cid, session_id, "user", question)
    await short_term.append(cid, session_id, "assistant", result.answer)
    await repo.touch_session(session_id)
    await repo.log_query(company_id=cid, raw_query=question, route=result.route, matched=matched)


# ── 동기 ──────────────────────────────────────────────────────────────
async def chat_sync(tenant: Tenant, *, session_id: str | None, message: str) -> ChatResult:
    sid = await _ensure_session(tenant, session_id)
    history = await short_term.history(tenant.company_id, sid)
    state = _mk_state(tenant, message, history)
    state = await run_plan(state)

    mode = state.get("mode")
    route = state.get("route", "rag")
    sources = state.get("sources", [])
    usage = state.get("usage", {"input_tokens": 0, "output_tokens": 0})

    if mode == "answer_ready":
        answer = state.get("answer", "")
        matched = True
    elif mode == "fail":
        answer = await _failure_message(tenant, message)
        sources, matched = [], False
    else:  # generate
        gen = await gen_node.generate(state)
        answer = gen.get("answer", "")
        usage = gen.get("usage", usage)
        # verify 는 선택(기본 OFF). chitchat·빈 컨텍스트는 검증 대상이 아니라 스킵.
        if (
            settings.verify_enabled
            and route != "chitchat"
            and state.get("retrieved_context", "").strip()
        ):
            grounded = await verify_node.verify(
                answer=answer,
                retrieved_context=state.get("retrieved_context", ""),
                business_info=state.get("business_info", ""),
            )
            if not grounded:
                answer = prompts.FALLBACK["no_ground"]
        matched = True

    result = ChatResult(
        session_id=sid, message_id=repo.new_id("msg"), route=route,
        answer=answer, sources=sources, usage=usage,
    )
    await _persist(tenant, sid, message, result, matched)
    return result


# ── 스트리밍 (SSE) ────────────────────────────────────────────────────
async def chat_stream(
    tenant: Tenant, *, session_id: str | None, message: str
) -> AsyncIterator[dict]:
    """SSE 이벤트 제너레이터. 각 dict: {"event": str, "data": dict}."""
    sid = await _ensure_session(tenant, session_id)
    history = await short_term.history(tenant.company_id, sid)
    state = _mk_state(tenant, message, history)
    state = await run_plan(state)

    mode = state.get("mode")
    route = state.get("route", "rag")
    message_id = repo.new_id("msg")
    sources = state.get("sources", [])
    usage = state.get("usage", {"input_tokens": 0, "output_tokens": 0})

    yield {"event": "meta", "data": {"session_id": sid, "message_id": message_id, "route": route}}

    answer_parts: list[str] = []
    matched = True
    try:
        if mode == "generate" and get_llm().available:
            system, messages = gen_node.build_messages(state)
            async for tok in get_llm().stream(
                system=system, messages=messages, model=model_for(Stage.GENERATE), max_tokens=1024
            ):
                answer_parts.append(tok)
                yield {"event": "token", "data": {"text": tok}}
            answer = "".join(answer_parts).strip() or prompts.FALLBACK["no_ground"]
        else:
            # answer_ready(faq/agent) / fail / LLM 미설정 → 완성 답변을 청크로 전송
            if mode == "answer_ready":
                answer = state.get("answer", "")
            elif mode == "fail":
                answer = await _failure_message(tenant, message)
                sources, matched = [], False
            else:  # generate 인데 LLM 없음
                answer = prompts.FALLBACK["no_ground"]
            for chunk in _chunk(answer):
                yield {"event": "token", "data": {"text": chunk}}
    except LLMTimeout:
        # 타임아웃: error 이벤트 + 폴백 메시지로 종료(§03 §1.5.1 streaming)
        answer = prompts.FALLBACK["timeout"]
        matched = False
        yield {"event": "error", "data": {"code": "LLM_TIMEOUT", "message": "응답 시간 초과"}}
        for chunk in _chunk(answer):
            yield {"event": "token", "data": {"text": chunk}}

    yield {"event": "sources", "data": {"sources": sources}}
    yield {"event": "done", "data": {"finish_reason": "stop", "usage": usage}}

    result = ChatResult(
        session_id=sid, message_id=message_id, route=route,
        answer="".join(answer_parts).strip() or answer, sources=sources, usage=usage,
    )
    await _persist(tenant, sid, message, result, matched)


def _chunk(text: str, size: int = 24):
    for i in range(0, len(text), size):
        yield text[i : i + size]
