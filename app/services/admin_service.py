"""관리자 서비스 (§03 §3.6) — FAQ 적재 / 인덱싱 트리거.

⚠️ 파일럿 단순화: 관리자 인증은 단일 공유 토큰(§deps.require_admin). 적재 대상
company_id 는 요청 body 로 받는다.

FAQ 적재는 **faq 벤더 서버가 소유**한다 — 오케스트레이터는 임베딩/벡터적재를 직접 하지 않고
faq 서버의 upsert_faq 도구에 위임한다(데이터 소유=벤더). faq_sources 이력/잡 기록은
오케스트레이터 메타DB 에 남긴다(감사/분석용).
"""
from __future__ import annotations

from app.db import postgres
from app.db import repositories as repo
from app.mcp import domain_client
from app.tenancy.registry import Tenant


async def upload_faq(tenant: Tenant, items: list[dict]) -> dict:
    """FAQ 적재 위임: faq 서버 upsert_faq 호출 + faq_sources 이력 기록(§04 §6)."""
    valid = [it for it in items if (it.get("question") or "").strip() and (it.get("answer") or "").strip()]

    # 1) 실제 임베딩·벡터 적재는 faq 벤더 서버에 위임
    result = await domain_client.call(
        tenant.faq.server_url, "upsert_faq", tenant.company_id, items=valid
    )
    accepted = result.get("accepted", 0) if result.get("success") is not False else 0

    # 2) 이력은 오케스트레이터 메타DB 에 기록(감사용)
    for it in valid:
        await _record_faq_source(
            tenant.company_id, it["question"].strip(), it["answer"].strip()
        )

    job_id = await repo.create_index_job(company_id=tenant.company_id, type_="faq", scope="incremental")
    return {"accepted": accepted, "job_id": job_id}


async def _record_faq_source(company_id: str, question: str, answer: str) -> None:
    """(company_id, question) 기준 멱등 — 같은 질문 재업로드 시 이력을 덮어쓴다."""
    async with (await postgres.init_pool()).connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM faq_sources WHERE company_id=%s AND question=%s",
                (company_id, question),
            )
            await cur.execute(
                "INSERT INTO faq_sources (company_id, question, answer, status) "
                "VALUES (%s,%s,%s,'embedded')",
                (company_id, question, answer),
            )


async def trigger_index(tenant: Tenant, *, source: str, scope: str) -> dict:
    """인덱싱 작업 등록(§03 §3.6). 파일럿은 작업만 기록(워커는 향후 구현)."""
    job_id = await repo.create_index_job(
        company_id=tenant.company_id, type_=source, scope=scope
    )
    return {"job_id": job_id}
