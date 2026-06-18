"""FAQ 인터셉트 노드 (계단형 필터 0단계, §01 §4.3, §08 §3).

LLM 이전에 실행된다. 임계값 이상 FAQ 가 있으면 즉답(answer_ready)으로 단락한다.
LLM 토큰을 거의 쓰지 않는 가장 빠른 경로다(§03 route=faq_intercept).

매칭은 **업체별 FAQ MCP 서버**(faq_server_url)에 MCP 프로토콜로 호출한다(A안).
서버 미기동/URL 없음이면 인프로세스 matcher 로 폴백한다(app/mcp/faq_client).
"""
from __future__ import annotations

from app.mcp import faq_client
from app.orchestration.state import RAGState


async def faq_intercept(state: RAGState) -> dict:
    res = await faq_client.match_faq(
        server_url=state.get("faq_server_url", ""),
        question=state["question"],
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
