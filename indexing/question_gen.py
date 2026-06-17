"""문서→질문 생성 (§01 §4.8, §07 §3.5) — 자동완성 풀.

각 청크에서 "답 가능한 질문"을 생성한다. LLM(Haiku)이 설정돼 있으면 LLM 으로,
없으면 규칙 기반 템플릿으로 degrade. 산출 질문은 autocomplete_q 임베딩 + Redis
prefix 풀에 적재된다(§07 §3.5). 후처리: 중복 제거.
"""
from __future__ import annotations

import json

from app.core.exceptions import AppError
from app.llm.client import get_llm
from app.llm.models import LIGHT

_SYSTEM = """다음 문장으로 '답할 수 있는' 자연스러운 한국어 질문을 1~2개 생성한다.
- 문장에 실제로 담긴 정보만 묻는다(지어내지 말 것).
- 너무 일반적이거나 모호한 질문은 제외.
출력(JSON): {"questions": ["...", "..."]}"""


async def generate_questions(chunk_text: str, *, max_q: int = 2) -> list[str]:
    llm = get_llm()
    if llm.available:
        try:
            data = await llm.complete_json(
                system=_SYSTEM, user=chunk_text, model=LIGHT, max_tokens=256
            )
            qs = (data or {}).get("questions") or []
            out = [q.strip() for q in qs if isinstance(q, str) and q.strip()]
            if out:
                return out[:max_q]
        except AppError:
            pass
    return _rule_based(chunk_text, max_q)


def _rule_based(chunk_text: str, max_q: int) -> list[str]:
    """LLM 미설정 폴백: 청크 앞부분을 키워드로 한 템플릿 질문."""
    head = chunk_text.split(":")[0].split(",")[0].strip()[:24]
    if not head:
        return []
    qs = [f"{head} 알려주세요", f"{head} 어떻게 되나요?"]
    return qs[:max_q]


def dedup(questions: list[str]) -> list[str]:
    seen, out = set(), []
    for q in questions:
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out
