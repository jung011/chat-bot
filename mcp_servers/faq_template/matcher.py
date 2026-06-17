"""FAQ 시맨틱 매칭 (§08 §3, §07 §4).

질문 임베딩 → 업체 FAQ 벡터검색 → 임계값 매칭 → 즉답/통과.
계단형 필터의 0단계(LLM 이전). 임계값 이상이면 등록된 answer 를 즉답한다.

코드 1벌, 설정만 다르게(§01 §6). config.yaml 의 company_id/collection/threshold 로
업체 인스턴스를 구성한다. 파일럿은 공용 Qdrant + 업체별 컬렉션(faq_<id>)으로 동작.
"""
from __future__ import annotations

from dataclasses import dataclass

from app.retrieval import vector_store


@dataclass
class FaqMatch:
    matched: bool
    answer: str | None = None
    question: str | None = None
    score: float = 0.0


async def match(question: str, *, collection: str, company_id: str, threshold: float) -> FaqMatch:
    """임계값 이상 FAQ 가 있으면 즉답(matched=True), 없으면 통과(matched=False)."""
    hits = await vector_store.search(
        collection, question, company_id=company_id, top_k=1, score_threshold=threshold
    )
    if not hits:
        return FaqMatch(matched=False)
    top = hits[0]
    return FaqMatch(
        matched=True,
        answer=top.payload.get("answer"),
        question=top.payload.get("question"),
        score=top.score,
    )
