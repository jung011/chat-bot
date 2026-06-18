"""라우팅 노드 (§06 §4.2).

질문을 chitchat/rag/agent 로 분류(계단형 필터 1단계 분기).

기본은 **규칙 기반**(route_mode="rule") — LLM 호출 0. 일반 질의를 rag 로 보내
RAG 경로의 LLM 호출을 2회(route+generate)→1회(generate)로 줄여 지연을 단축한다.
규칙은 보수적: 인사만 chitchat, 명확한 도구 신호만 agent, 그 외 기본 rag.

route_mode:
- "rule"  (기본): 규칙만.
- "llm"        : 기존 Haiku 분류(LLM 호출 1회).
- "hybrid"     : 규칙이 기본값(rag)일 때만 LLM 로 재확인(정확도↑, 호출 1회 추가).
"""
from __future__ import annotations

from app.core.config import settings
from app.core.exceptions import AppError
from app.llm.client import get_llm
from app.llm.models import Stage, model_for
from app.orchestration import prompts
from app.orchestration.state import RAGState

_VALID = {"chitchat", "rag", "agent"}

# 인사/잡담 신호
_GREETINGS = ("안녕", "하이", "ㅎㅇ", "반가", "고마", "감사", "잘 지내", "좋은 아침", "좋은 하루", "굿모닝", "수고")
# 정보 요청 신호(인사와 함께 있으면 chitchat 아님)
_INFO = ("가격", "얼마", "메뉴", "배달", "영업", "시간", "위치", "주소", "주문", "추천", "결제", "주차", "전화", "메뉴")
# 도구가 필요한 신호(백엔드 API/DB 조회가 필요한 — ETA·주문/결제 방법·메뉴가격·주문상태).
# '예약'은 전용 도구가 없고 FAQ 주제라 제외(→ rag 에서 FAQ 검색으로 처리).
_AGENT = (
    "예상", "배달시간", "얼마나 걸", "얼마나 오래", "주문 방법", "주문방법", "결제수단", "결제 수단",
    "가격", "얼마", "메뉴",                        # 메뉴/가격 → 백엔드 DB 조회 도구
    "주문 상태", "주문번호", "주문 번호", "배송", "어디쯤",  # 주문 상태 → 라이브 DB 조회 도구
)


def rule_route(question: str) -> str:
    q = question.strip()
    if any(g in q for g in _GREETINGS) and not any(k in q for k in _INFO):
        return "chitchat"
    if any(a in q for a in _AGENT):
        return "agent"
    return "rag"


async def _llm_route(question: str) -> str | None:
    llm = get_llm()
    if not llm.available:
        return None
    try:
        data = await llm.complete_json(
            system=prompts.ROUTE_SYSTEM, user=question, model=model_for(Stage.ROUTE)
        )
    except AppError:
        return None
    r = (data or {}).get("route")
    return r if r in _VALID else None


async def route(state: RAGState) -> dict:
    question = state.get("rewritten") or state["question"]
    mode = settings.route_mode

    if mode == "llm":
        return {"route": (await _llm_route(question)) or "rag"}

    r = rule_route(question)
    if mode == "hybrid" and r == "rag":
        # 규칙이 기본값(rag)이면 LLM 으로 한 번 더 확인(호출 1회 추가)
        r = (await _llm_route(question)) or "rag"
    return {"route": r}
