"""FAQ 인터셉트 노드 (계단형 필터 0단계, §01 §4.3, §08 §3).

LLM 이전에 실행된다. 임계값 이상 FAQ 가 있으면 즉답(answer_ready)으로 단락한다.
LLM 토큰을 거의 쓰지 않는 가장 빠른 경로다(§03 route=faq_intercept).

매칭은 **업체별 FAQ MCP 서버**(faq_server_url)에 MCP 프로토콜로 호출한다(A안).
서버 미기동/URL 없음이면 인프로세스 matcher 로 폴백한다(app/mcp/faq_client).
"""
from __future__ import annotations

from app.mcp import faq_client
from app.orchestration.state import RAGState

# 복합 질문 신호(여러 의도 결합) — 0단계 단답으로 끊지 말고 rag(FAQ 다건 검색)로 보낸다.
# 실제 임베더는 복합 질문의 한 절(節)에도 단일 FAQ 가 높은 점수로 매칭되어,
# 임계값만으로는 "단일 질문"과 "복합 질문의 한 절"을 구분하지 못한다(§08 §3 주석).
_COMPOUND_MARKERS = ("그리고", "둘 다", "되고", "있고", "이랑", "랑 ", "하고", " 및 ", " 와 ", " 과 ")


def _looks_compound(q: str) -> bool:
    if (q.count("?") + q.count("？")) > 1:  # 두 문장 이상
        return True
    return any(m in q for m in _COMPOUND_MARKERS)


async def faq_intercept(state: RAGState) -> dict:
    question = state["question"]
    # 복합 질문이면 0단계 즉답을 건너뛴다(한쪽 의도만 답하는 오즉답 방지) → rag 가 FAQ 다건 처리
    if _looks_compound(question):
        return {}
    res = await faq_client.match_faq(
        server_url=state.get("faq_server_url", ""),
        question=question,
    )
    if res.get("matched") and res.get("answer"):
        return {
            "route": "faq_intercept",
            "mode": "answer_ready",
            "answer": res["answer"],
            "sources": [
                {"type": "faq", "title": res.get("question") or "FAQ", "score": round(res.get("score", 0.0), 3)}
            ],
        }
    return {}  # 통과 → 다음 단계
