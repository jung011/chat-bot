"""검증 노드 (§06 §4.5, 선택) — Haiku.

생성 답변이 컨텍스트에 근거하는지 점검한다. grounded=false 면 호출부가
"확인 어려움" 폴백으로 대체한다. 컨텍스트가 없거나(LLM 미설정/chitchat) 검증
불가하면 통과(grounded=True)로 간주한다.
"""
from __future__ import annotations

from app.core.exceptions import AppError
from app.llm.client import get_llm
from app.llm.models import Stage, model_for
from app.orchestration import prompts


async def verify(*, answer: str, retrieved_context: str) -> bool:
    """근거 충실성 평가. 평가 불가/오류 시 True(통과)."""
    llm = get_llm()
    if not llm.available or not retrieved_context.strip():
        return True
    try:
        data = await llm.complete_json(
            system=prompts.VERIFY_SYSTEM,
            user=prompts.VERIFY_USER.format(retrieved_context=retrieved_context, answer=answer),
            model=model_for(Stage.VERIFY),
        )
    except AppError:
        return True
    if data is None:
        return True
    return bool(data.get("grounded", True))
