"""인덱싱 파이프라인 (§07 §3) — 오프라인.

원본 → 파싱 → 청킹 → 임베딩 → 벡터DB 적재(documents, company_id 태그)
        └→ 질문 생성(LLM) → autocomplete_q + 자동완성 prefix 풀(Redis) 적재
"""
from __future__ import annotations

import secrets

from app.autocomplete import suggester
from app.retrieval import vector_store
from app.retrieval.embedder import get_embedder
from indexing import chunking, question_gen
from indexing.parsers import parse_text

DOCUMENTS_COLLECTION = "documents"
AUTOCOMPLETE_COLLECTION = "autocomplete_q"


async def index_documents(company_id: str, docs: list[dict]) -> dict:
    """docs: [{doc_id, title, category, text, source_uri}]. 청크 적재 + 질문 생성."""
    await vector_store.ensure_collection(DOCUMENTS_COLLECTION)
    await vector_store.ensure_collection(AUTOCOMPLETE_COLLECTION)
    emb = get_embedder()

    doc_points: list[dict] = []
    acq_points: list[dict] = []
    pool: list[dict] = []

    for doc in docs:
        text = parse_text(doc["text"])
        for idx, ch in enumerate(chunking.chunk(text)):
            doc_points.append(
                {
                    "id": f"{company_id}_{doc['doc_id']}_{idx}",
                    "vector": emb.embed(ch),
                    "payload": {
                        "company_id": company_id,
                        "doc_id": doc["doc_id"],
                        "chunk_index": idx,
                        "text": ch,
                        "title": doc.get("title", ""),
                        "category": doc.get("category", ""),
                        "source_uri": doc.get("source_uri", ""),
                    },
                }
            )
            # 자동완성 질문 생성
            for q in question_gen.dedup(await question_gen.generate_questions(ch)):
                acq_points.append(
                    {
                        "id": f"acq_{company_id}_{secrets.token_hex(8)}",
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

    await vector_store.upsert(DOCUMENTS_COLLECTION, doc_points)
    await vector_store.upsert(AUTOCOMPLETE_COLLECTION, acq_points)
    await _merge_pool(company_id, pool)
    return {"chunks": len(doc_points), "questions": len(acq_points)}


async def index_tools(catalog: list[dict]) -> int:
    """도구 description 을 tools 컬렉션에 적재(Tool RAG, §04 §3.1)."""
    await vector_store.ensure_collection("tools")
    emb = get_embedder()
    points = [
        {
            "id": f"tool_{t['name']}",
            "vector": emb.embed(t["description"]),
            "payload": t,
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
