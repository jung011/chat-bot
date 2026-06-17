"""자동완성 추천 (§01 §4.8, §03 §3.3, §07 §3.5).

후보 = "반드시 답할 수 있는 질문"(문서/FAQ 에서 생성). 검색 실패가 구조적으로 거의 없다.
- 후보 풀은 Redis key `ac:{company_id}` 에 JSON 배열 [{text, source}] 로 저장(prefix 주력).
- prefix 매칭 우선, 부족하면 시맨틱 보강(autocomplete_q 컬렉션, §04 §3.1).
- 모든 후보는 company_id 로 격리.
"""
from __future__ import annotations

import json

from app.db import redis_client
from app.retrieval import vector_store

AUTOCOMPLETE_COLLECTION = "autocomplete_q"


def _key(company_id: str) -> str:
    return f"ac:{company_id}"


async def load_pool(company_id: str) -> list[dict]:
    raw = await redis_client.get_client().get(_key(company_id))
    if not raw:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return []


async def save_pool(company_id: str, items: list[dict]) -> None:
    await redis_client.get_client().set(_key(company_id), json.dumps(items, ensure_ascii=False))


async def suggest(company_id: str, q: str, limit: int = 8) -> list[dict]:
    """prefix(주력) + 시맨틱(보강). 각 원소 {text, source}."""
    pool = await load_pool(company_id)
    ql = q.strip().lower()

    if not ql:  # 빈 입력 → 풀 상위
        return pool[:limit]

    # 1) prefix 우선, 2) 부분일치
    starts = [s for s in pool if s["text"].lower().startswith(ql)]
    contains = [s for s in pool if ql in s["text"].lower() and s not in starts]
    results = starts + contains

    # 3) 부족하면 시맨틱 보강
    if len(results) < limit:
        seen = {s["text"] for s in results}
        hits = await vector_store.search(
            AUTOCOMPLETE_COLLECTION, q, company_id=company_id, top_k=limit
        )
        for h in hits:
            text = h.payload.get("question")
            if text and text not in seen:
                results.append({"text": text, "source": "document"})
                seen.add(text)

    return results[:limit]


async def recommend(company_id: str, q: str, n: int = 3) -> list[str]:
    """답변 실패 시 추천 질문(§06 §10.2). 관련 후보 우선, 없으면 풀 상위."""
    sugg = await suggest(company_id, q, limit=n)
    if sugg:
        return [s["text"] for s in sugg]
    pool = await load_pool(company_id)
    return [s["text"] for s in pool[:n]]
