"""채팅 서비스 (§03 §3.1~3.2, §06).

계단형 필터 오케스트레이션을 호출하고, 세션/메시지 영속화·로깅·폴백을 처리한다.
- chat_sync: 한 번에 답변(비스트리밍).
- chat_stream: SSE 이벤트 제너레이터(meta→token*→sources→done|error).
두 경로 모두 동일한 plan 그래프 결과를 공유한다(§02 graph.py).
"""
from __future__ import annotations

import asyncio
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
async def _plan_and_answer(tenant: Tenant, message: str, history: list[dict]):
    """오케스트레이션 + 답변 생성. (route, answer, sources, usage, matched) 반환.

    요청 단위 타임아웃으로 감쌀 수 있도록 LLM 포함 작업을 한 코루틴으로 묶는다.
    """
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

    return route, answer, sources, usage, matched


async def chat_sync(tenant: Tenant, *, session_id: str | None, message: str) -> ChatResult:
    sid = await _ensure_session(tenant, session_id)
    history = await short_term.history(tenant.company_id, sid)

    timeout = settings.request_timeout_seconds
    coro = _plan_and_answer(tenant, message, history)
    try:
        if timeout and timeout > 0:
            route, answer, sources, usage, matched = await asyncio.wait_for(coro, timeout)
        else:
            route, answer, sources, usage, matched = await coro
    except asyncio.TimeoutError:
        # 요청 전체 타임아웃 — graceful 폴백(§06 §10.3). 진행 중 LLM 서브프로세스는
        # 자체 llm_timeout_seconds 로 정리된다.
        route = "timeout"
        answer = prompts.FALLBACK["timeout"]
        sources, usage, matched = [], {"input_tokens": 0, "output_tokens": 0}, False

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
    """SSE 이벤트 제너레이터. 각 dict: {"event": str, "data": dict}.

    요청 전체 타임아웃(request_timeout_seconds)을 두 지점에 적용한다:
      A) run_plan(첫 토큰 전 검색/도구) 를 wait_for 로 감쌈 → 초과 시 즉시 timeout 폴백.
      C) 토큰 스트리밍 중 누적 deadline 을 매 토큰마다 확인 → 초과 시 error 이벤트로 중단.
    (이미 일부 토큰을 보낸 뒤 C 가 발동하면, 보낸 토큰 + 중단 안내가 함께 남는다.)
    """
    sid = await _ensure_session(tenant, session_id)
    history = await short_term.history(tenant.company_id, sid)

    timeout = settings.request_timeout_seconds
    loop = asyncio.get_event_loop()
    deadline = (loop.time() + timeout) if timeout and timeout > 0 else None

    def _remaining() -> float | None:
        return None if deadline is None else max(0.0, deadline - loop.time())

    # ── A: 첫 토큰 전(run_plan) 타임아웃 ──
    state = _mk_state(tenant, message, history)
    try:
        if deadline is None:
            state = await run_plan(state)
        else:
            state = await asyncio.wait_for(run_plan(state), timeout=_remaining())
    except asyncio.TimeoutError:
        message_id = repo.new_id("msg")
        answer = prompts.FALLBACK["timeout"]
        yield {"event": "meta", "data": {"session_id": sid, "message_id": message_id, "route": "timeout"}}
        yield {"event": "error", "data": {"code": "REQUEST_TIMEOUT", "message": "응답 시간 초과"}}
        for chunk in _chunk(answer):
            yield {"event": "token", "data": {"text": chunk}}
        yield {"event": "sources", "data": {"sources": []}}
        yield {"event": "done", "data": {"finish_reason": "timeout", "usage": {"input_tokens": 0, "output_tokens": 0}}}
        result = ChatResult(
            session_id=sid, message_id=message_id, route="timeout",
            answer=answer, sources=[], usage={"input_tokens": 0, "output_tokens": 0},
        )
        await _persist(tenant, sid, message, result, False)
        return

    mode = state.get("mode")
    route = state.get("route", "rag")
    message_id = repo.new_id("msg")
    sources = state.get("sources", [])
    usage = state.get("usage", {"input_tokens": 0, "output_tokens": 0})

    yield {"event": "meta", "data": {"session_id": sid, "message_id": message_id, "route": route}}

    answer_parts: list[str] = []
    matched = True
    timed_out = False
    agen = None
    try:
        if mode == "generate" and get_llm().available:
            system, messages = gen_node.build_messages(state)
            agen = get_llm().stream(
                system=system, messages=messages, model=model_for(Stage.GENERATE), max_tokens=1024
            )
            # ── C: 토큰마다 남은 예산 확인(누적 deadline) ──
            while True:
                rem = _remaining()
                if rem is not None and rem <= 0:
                    raise asyncio.TimeoutError
                try:
                    nxt = agen.__anext__()
                    tok = await (nxt if rem is None else asyncio.wait_for(nxt, timeout=rem))
                except StopAsyncIteration:
                    break
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
        # 호출당 타임아웃: error 이벤트 + 폴백 메시지로 종료(§03 §1.5.1 streaming)
        answer = prompts.FALLBACK["timeout"]
        matched = False
        yield {"event": "error", "data": {"code": "LLM_TIMEOUT", "message": "응답 시간 초과"}}
        for chunk in _chunk(answer):
            yield {"event": "token", "data": {"text": chunk}}
    except asyncio.TimeoutError:
        # C: 요청 전체 예산 초과 — 이미 보낸 토큰 뒤에 중단 안내를 덧붙인다.
        timed_out, matched = True, False
        if agen is not None:
            await agen.aclose()
        note = prompts.FALLBACK["timeout"]
        yield {"event": "error", "data": {"code": "REQUEST_TIMEOUT", "message": "응답 시간 초과"}}
        for chunk in _chunk(note):
            yield {"event": "token", "data": {"text": chunk}}
        sent = "".join(answer_parts).strip()
        answer = (sent + "\n\n" + note) if sent else note

    yield {"event": "sources", "data": {"sources": sources}}
    yield {"event": "done", "data": {"finish_reason": "timeout" if timed_out else "stop", "usage": usage}}

    result = ChatResult(
        session_id=sid, message_id=message_id, route=("timeout" if timed_out else route),
        answer="".join(answer_parts).strip() or answer, sources=sources, usage=usage,
    )
    await _persist(tenant, sid, message, result, matched)


def _chunk(text: str, size: int = 24):
    for i in range(0, len(text), size):
        yield text[i : i + size]
