"""인덱싱 파이프라인 (§07 §3) — 오프라인 (오케스트레이터 측).

문서 본문 자체의 적재(documents 컬렉션)는 **general 벤더 서버가 소유**(ingest_documents 도구).
오케스트레이터는 자기 UX 기능인 **자동완성(autocomplete_q + prefix 풀)** 만 문서에서 생성한다
(질문 생성은 LLM 필요 — 벤더 서버에는 LLM 이 없으므로 오케스트레이터가 담당).
"""
from __future__ import annotations

import hashlib

from app.autocomplete import suggester
from app.retrieval import vector_store
from app.retrieval.embedder import get_embedder
from indexing import chunking, question_gen
from indexing.parsers import parse_text

AUTOCOMPLETE_COLLECTION = "autocomplete_q"


async def generate_autocomplete(company_id: str, docs: list[dict]) -> dict:
    """문서에서 자동완성 질문을 생성해 autocomplete_q + prefix 풀에 적재(오케스트레이터 소유)."""
    await vector_store.ensure_collection(AUTOCOMPLETE_COLLECTION)
    await vector_store.ensure_company_index(AUTOCOMPLETE_COLLECTION)
    emb = get_embedder()

    acq_points: list[dict] = []
    pool: list[dict] = []
    for doc in docs:
        for ch in chunking.chunk(parse_text(doc["text"])):
            for q in question_gen.dedup(await question_gen.generate_questions(ch)):
                qhash = hashlib.sha1(q.encode("utf-8")).hexdigest()[:16]
                acq_points.append(
                    {
                        "id": f"acq_{company_id}_{qhash}",
                        "vector": emb.embed(q),
                        "payload": {
                            "company_id": company_id,
                            "question": q,
                            "origin_doc_id": doc["doc_id"],
                            "popularity": 0,
                        },
                    }
                )
                pool.append({"text": q, "source": "document"})

    await vector_store.upsert(AUTOCOMPLETE_COLLECTION, acq_points)
    await _merge_pool(company_id, pool)
    return {"questions": len(acq_points)}


async def index_tools(catalog: list[dict], company_id: str) -> int:
    """도구 description 을 tools 컬렉션에 적재(Tool RAG, §04 §3.1).

    업체별로 적재한다(payload.company_id 태깅). 같은 도구라도 업체별 포인트로 나뉘어
    retrieve_tools(company_id=...) 가 그 업체 도구만 검색하도록 한다(업체별 일반 서버 대응).
    """
    await vector_store.ensure_collection("tools")
    await vector_store.ensure_company_index("tools")
    emb = get_embedder()
    points = [
        {
            "id": f"tool_{company_id}_{t['name']}",
            "vector": emb.embed(t["description"]),
            "payload": {**t, "company_id": company_id},
        }
        for t in catalog
    ]
    return await vector_store.upsert("tools", points)


async def add_to_autocomplete_pool(company_id: str, items: list[dict]) -> None:
    """FAQ 질문 등 추가 후보를 풀에 병합(§03 source: faq)."""
    await _merge_pool(company_id, items)


async def _merge_pool(company_id: str, new_items: list[dict]) -> None:
    existing = await suggester.load_pool(company_id)
    seen = {i["text"] for i in existing}
    for it in new_items:
        if it["text"] not in seen:
            existing.append(it)
            seen.add(it["text"])
    await suggester.save_pool(company_id, existing)
