"""오케스트레이션 그래프 (§01 계단형 필터, §02 orchestration/graph.py).

LangGraph StateGraph 로 결정·검색·도구 파이프라인을 구성한다:

    faq_intercept ─(matched)→ END(answer_ready)
        │(통과)
        ▼
      rewrite → route ─┬─ chitchat → END(generate)
                       ├─ rag      → retrieve → END(generate | fail)
                       └─ agent    → agent    → END(answer_ready | fail)

최종 답변 생성(generate)·검증(verify)은 이 그래프 다음 단계로 서비스가 호출한다.
이렇게 분리하면 스트리밍(/chat 실시간 토큰)과 동기(/chat/sync)가 동일한 그래프
결과(컨텍스트/route/mode)를 공유한다(generate.py·verify.py 의 함수를 재사용).
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.orchestration.nodes.faq import faq_intercept
from app.orchestration.nodes.rewrite import rewrite
from app.orchestration.nodes.route import route as route_node
from app.orchestration.nodes.tool_select import agent, prep_chitchat, retrieve_documents
from app.orchestration.state import RAGState


def _after_faq(state: RAGState) -> str:
    return "end" if state.get("mode") == "answer_ready" else "continue"


def _after_route(state: RAGState) -> str:
    r = state.get("route", "rag")
    return r if r in ("chitchat", "rag", "agent") else "rag"


def build_plan_graph():
    g = StateGraph(RAGState)
    g.add_node("faq", faq_intercept)
    g.add_node("rewrite", rewrite)
    g.add_node("route", route_node)
    g.add_node("chitchat", prep_chitchat)
    g.add_node("retrieve", retrieve_documents)
    g.add_node("agent", agent)

    g.set_entry_point("faq")
    g.add_conditional_edges("faq", _after_faq, {"end": END, "continue": "rewrite"})
    g.add_edge("rewrite", "route")
    g.add_conditional_edges(
        "route", _after_route, {"chitchat": "chitchat", "rag": "retrieve", "agent": "agent"}
    )
    g.add_edge("chitchat", END)
    g.add_edge("retrieve", END)
    g.add_edge("agent", END)
    return g.compile()


_plan_graph = None


def get_plan_graph():
    global _plan_graph
    if _plan_graph is None:
        _plan_graph = build_plan_graph()
    return _plan_graph


async def run_plan(state: RAGState) -> RAGState:
    """그래프 실행 → 갱신된 상태 반환(생성 직전까지)."""
    return await get_plan_graph().ainvoke(state)
