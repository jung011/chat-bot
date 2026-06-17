"""질문 재작성 노드 (§06 §4.1) — Haiku.

대화 맥락의 지시어를 구체화해 검색 가능한 독립 질문으로 만든다.
첫 질문이거나 LLM 미설정 시 원문을 그대로 사용(graceful degrade).
"""
from __future__ import annotations

from app.core.exceptions import AppError
from app.llm.client import get_llm
from app.llm.models import Stage, model_for
from app.memory import short_term
from app.orchestration import prompts
from app.orchestration.state import RAGState, add_usage


async def rewrite(state: RAGState) -> dict:
    history = state.get("history", [])
    llm = get_llm()
    if not history or not llm.available:
        return {"rewritten": state["question"]}

    user = prompts.REWRITE_USER.format(
        history=short_term.history_text(history), question=state["question"]
    )
    try:
        comp = await llm.complete(
            system=prompts.REWRITE_SYSTEM,
            messages=[{"role": "user", "content": user}],
            model=model_for(Stage.REWRITE),
            max_tokens=256,
        )
    except AppError:
        return {"rewritten": state["question"]}

    text = comp.text.strip() or state["question"]
    return {
        "rewritten": text,
        "usage": add_usage(state, comp.input_tokens, comp.output_tokens),
    }
