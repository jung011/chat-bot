"""FAQ 시맨틱 매칭 — 질문 임베딩 → 벡터검색 → 임계값 매칭."""
from __future__ import annotations

from app.config import settings
from app.embedder import HashEmbedder
from app.vector_store import search, search_threshold

_embedder = HashEmbedder(settings.embedding_dim)


async def search_faq(question: str, top_k: int = 5) -> list[dict]:
    """질문과 유사한 FAQ 상위 K건(임계값 없음) — 생성 컨텍스트용."""
    hits = await search(settings.faq_collection, _embedder.embed(question), settings.company_id, top_k)
    return [
        {"question": h.payload.get("question"), "answer": h.payload.get("answer"), "score": round(h.score, 4)}
        for h in hits
    ]


async def match(question: str) -> dict:
    """{matched, answer?, score, question?} 반환."""
    vector = _embedder.embed(question)
    hit = await search_threshold(
        settings.faq_collection, vector, settings.company_id, settings.faq_threshold
    )
    if hit is None:
        return {"matched": False, "score": 0.0}
    return {
        "matched": True,
        "answer": hit.payload.get("answer"),
        "question": hit.payload.get("question"),
        "score": round(hit.score, 4),
    }
