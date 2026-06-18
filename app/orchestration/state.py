"""오케스트레이션 상태 (§02 orchestration/state.py).

계단형 필터(§01)를 따라 노드들이 채워 나가는 공유 상태.
LangGraph StateGraph 의 state schema 로 사용한다(노드는 부분 dict 를 반환).
"""
from __future__ import annotations

from typing import Any, Literal, TypedDict

# 처리 경로(§03 meta.route): mode 와 함께 분석/디버깅에 사용
RouteName = Literal["faq_intercept", "chitchat", "rag", "agent"]
# 후처리 분기: 즉답 준비됨 / LLM 생성 필요 / 답변 실패
Mode = Literal["answer_ready", "generate", "fail"]


class RAGState(TypedDict, total=False):
    # 입력 (서비스가 채움)
    company_id: str
    question: str                 # 원본 질문
    history: list[dict]           # [{role, content}]
    persona: str                  # 업체 페르소나(§06 §3)
    business_info: str            # 업체 영업정보 텍스트(§06 §4.4)
    faq_server_url: str           # 업체별 FAQ MCP 서버 URL(A안). 매칭은 서버가 담당.
    general_server_url: str       # 업체별 일반(도메인) MCP 서버 URL(A안). 비면 인프로세스.
    doc_top_k: int
    doc_top_n: int
    tool_top_k: int

    # 처리 중 (노드가 채움)
    rewritten: str                # 재작성된 독립 질문
    route: RouteName
    sources: list[dict]           # 근거(FAQ/문서/도구)
    retrieved_context: str        # 생성에 투입할 컨텍스트
    tool_trace: list[dict]        # 실행된 도구 기록(디버깅)
    iters: int

    # 출력
    mode: Mode
    answer: str                   # mode in {answer_ready, fail} 이면 채워짐
    fail_reason: str              # 실패 유형(A/B/C/D, §06 §10.1)
    usage: dict[str, int]         # {input_tokens, output_tokens}


def initial_state(
    *,
    company_id: str,
    question: str,
    history: list[dict],
    persona: str,
    business_info: str,
    faq_server_url: str,
    general_server_url: str,
    doc_top_k: int,
    doc_top_n: int,
    tool_top_k: int,
) -> RAGState:
    return RAGState(
        company_id=company_id,
        question=question,
        history=history,
        persona=persona,
        business_info=business_info,
        faq_server_url=faq_server_url,
        general_server_url=general_server_url,
        doc_top_k=doc_top_k,
        doc_top_n=doc_top_n,
        tool_top_k=tool_top_k,
        rewritten=question,
        sources=[],
        retrieved_context="",
        tool_trace=[],
        iters=0,
        usage={"input_tokens": 0, "output_tokens": 0},
    )


def add_usage(state: RAGState, input_tokens: int, output_tokens: int) -> dict:
    u = dict(state.get("usage", {"input_tokens": 0, "output_tokens": 0}))
    u["input_tokens"] += input_tokens
    u["output_tokens"] += output_tokens
    return u
