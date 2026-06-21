"""FAQ 적재 — 이 서버가 자기 FAQ 컬렉션을 소유·관리한다(벤더 적재).

질문을 자체 임베더로 임베딩해 자기 faq 컬렉션에 upsert. 결정적 ID(질문 해시)로 멱등.
오케스트레이터가 upsert_faq 도구를 통해 위임 호출한다(데이터 소유=벤더).
"""
from __future__ import annotations

import hashlib

from app.config import settings
from app.embedder import get_embedder
from app.vector_store import ensure_collection, upsert


async def upsert_faq(items: list[dict]) -> dict:
    """items: [{question, answer, category?}] → 자기 faq 컬렉션에 적재. {accepted} 반환."""
    await ensure_collection(settings.faq_collection, settings.embedding_dim)
    points, accepted = [], 0
    for it in items:
        q = (it.get("question") or "").strip()
        a = (it.get("answer") or "").strip()
        if not q or not a:
            continue
        qhash = hashlib.sha1(q.encode("utf-8")).hexdigest()[:16]
        points.append(
            {
                "id": f"faq_{settings.company_id}_{qhash}",
                "vector": get_embedder().embed(q),
                "payload": {
                    "company_id": settings.company_id,
                    "question": q,
                    "answer": a,
                    "category": it.get("category", "general"),
                    "source": "manual",
                },
            }
        )
        accepted += 1
    await upsert(settings.faq_collection, points)
    return {"accepted": accepted}
