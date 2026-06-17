"""FAQ 인터셉트 노드 (계단형 필터 0단계, §01 §4.3, §08 §3).

LLM 이전에 실행된다. 임계값 이상 FAQ 가 있으면 즉답(answer_ready)으로 단락한다.
LLM 토큰을 거의 쓰지 않는 가장 빠른 경로다(§03 route=faq_intercept).
"""
from __future__ import annotations

from app.orchestration.state import RAGState
from mcp_servers.faq_template import matcher


async def faq_intercept(state: RAGState) -> dict:
    m = await matcher.match(
        state["question"],
        collection=state["faq_collection"],
        company_id=state["company_id"],
        threshold=state["faq_threshold"],
    )
    if m.matched and m.answer:
        return {
            "route": "faq_intercept",
            "mode": "answer_ready",
            "answer": m.answer,
            "sources": [
                {"type": "faq", "title": m.question or "FAQ", "score": round(m.score, 3)}
            ],
        }
    return {}  # 통과 → 다음 단계
