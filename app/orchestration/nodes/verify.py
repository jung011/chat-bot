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


async def verify(*, answer: str, retrieved_context: str, business_info: str = "") -> bool:
    """근거 충실성 평가. 평가 불가/오류 시 True(통과).

    근거는 검색 컨텍스트 + 업체 영업정보(전화/주소/영업시간 등)를 모두 포함한다.
    (생성 프롬프트가 두 가지를 모두 근거로 쓰므로, 검증도 동일 근거로 평가해야
    영업정보 인용을 '근거 없음'으로 오판하지 않는다.)
    """
    llm = get_llm()
    grounding = retrieved_context
    if business_info.strip():
        grounding = f"{retrieved_context}\n[업체 영업정보]\n{business_info}"
    if not llm.available or not grounding.strip():
        return True
    try:
        data = await llm.complete_json(
            system=prompts.VERIFY_SYSTEM,
            user=prompts.VERIFY_USER.format(retrieved_context=grounding, answer=answer),
            model=model_for(Stage.VERIFY),
        )
    except AppError:
        return True
    if data is None:
        return True
    return bool(data.get("grounded", True))
