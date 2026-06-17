"""답변 생성 노드 (§06 §4.4) — Sonnet.

`build_messages` 로 (system, messages) 를 조립한다. 서비스는 이를 이용해
- 스트리밍(/chat): llm.stream() 으로 실시간 토큰 전송
- 동기(/chat/sync): generate() 로 한 번에 생성
둘 다 동일 프롬프트를 공유한다. route=chitchat 이면 검색 컨텍스트 없이 잡담 프롬프트 사용.
"""
from __future__ import annotations

from app.llm.client import get_llm
from app.llm.models import Stage, model_for
from app.memory import short_term
from app.orchestration import prompts
from app.orchestration.state import RAGState, add_usage


def build_messages(state: RAGState) -> tuple[str, list[dict]]:
    persona = state.get("persona", "")
    business_info = state.get("business_info", "")
    question = state.get("rewritten") or state["question"]
    history = short_term.history_text(state.get("history", []))

    if state.get("route") == "chitchat":
        system = prompts.CHITCHAT_SYSTEM.format(persona=persona, business_info=business_info)
    else:
        system = prompts.GENERATE_SYSTEM.format(
            persona=persona,
            retrieved_context=state.get("retrieved_context", ""),
            business_info=business_info,
        )
    user = prompts.GENERATE_USER.format(history=history or "(없음)", question=question)
    return system, [{"role": "user", "content": user}]


async def generate(state: RAGState) -> dict:
    """동기 생성: LLM 미설정이면 폴백 문구(§06 §10 — 근거 없음)."""
    llm = get_llm()
    if not llm.available:
        return {"mode": "answer_ready", "answer": prompts.FALLBACK["no_ground"]}

    system, messages = build_messages(state)
    comp = await llm.complete(
        system=system, messages=messages, model=model_for(Stage.GENERATE), max_tokens=1024
    )
    return {
        "mode": "answer_ready",
        "answer": comp.text.strip() or prompts.FALLBACK["no_ground"],
        "usage": add_usage(state, comp.input_tokens, comp.output_tokens),
    }
