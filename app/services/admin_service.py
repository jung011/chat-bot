"""관리자 서비스 (§03 §3.6) — FAQ 적재 / 인덱싱 트리거.

⚠️ 파일럿 단순화: 관리자 인증은 단일 공유 토큰(§deps.require_admin). 적재 대상
company_id 는 요청 body 로 받는다. 운영에서는 admins 테이블 기반 per-company 토큰의
company_id 로 결정한다(§03 §3.6 "토큰의 company_id").
"""
from __future__ import annotations

import secrets

from app.db import postgres
from app.db import repositories as repo
from app.retrieval import vector_store
from app.retrieval.embedder import get_embedder
from app.tenancy.registry import Tenant


async def upload_faq(tenant: Tenant, items: list[dict]) -> dict:
    """FAQ 적재: faq_<company> 컬렉션 임베딩 + faq_sources 이력(§04 §6 FAQ 적재)."""
    collection = tenant.faq.collection
    await vector_store.ensure_collection(collection)
    emb = get_embedder()

    points, accepted = [], 0
    for it in items:
        question = (it.get("question") or "").strip()
        answer = (it.get("answer") or "").strip()
        if not question or not answer:
            continue
        vector_id = f"faq_{tenant.company_id}_{secrets.token_hex(8)}"
        points.append(
            {
                "id": vector_id,
                "vector": emb.embed(question),
                "payload": {
                    "company_id": tenant.company_id,
                    "question": question,
                    "answer": answer,
                    "category": it.get("category", "general"),
                    "source": "manual",
                },
            }
        )
        await _record_faq_source(tenant.company_id, question, answer, vector_id)
        accepted += 1

    if points:
        await vector_store.upsert(collection, points)

    job_id = await repo.create_index_job(company_id=tenant.company_id, type_="faq", scope="incremental")
    return {"accepted": accepted, "job_id": job_id}


async def _record_faq_source(company_id: str, question: str, answer: str, vector_id: str) -> None:
    async with (await postgres.init_pool()).connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO faq_sources (company_id, question, answer, status, vector_id) "
                "VALUES (%s,%s,%s,'embedded',%s)",
                (company_id, question, answer, vector_id),
            )


async def trigger_index(tenant: Tenant, *, source: str, scope: str) -> dict:
    """인덱싱 작업 등록(§03 §3.6). 파일럿은 작업만 기록(워커는 향후 구현)."""
    job_id = await repo.create_index_job(
        company_id=tenant.company_id, type_=source, scope=scope
    )
    return {"job_id": job_id}
