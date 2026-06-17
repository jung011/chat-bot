"""데모 시드 — 피자집/중국집/치킨집 메뉴·정책·FAQ·도구를 적재한다.

실행: python scripts/seed_demo.py
- documents 컬렉션: 메뉴/정책 청크 (+ 자동완성 질문 생성)
- faq_<company> 컬렉션: 정형 FAQ (즉답 인터셉트용)
- tools 컬렉션: 도메인 도구 description (Tool RAG)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import postgres, redis_client  # noqa: E402
from app.mcp import client as mcp_client  # noqa: E402
from app.retrieval import vector_store  # noqa: E402
from app.services import admin_service  # noqa: E402
from app.tenancy import router as tenant_router  # noqa: E402
from indexing import pipeline  # noqa: E402

# ── 문서(메뉴/정책) ────────────────────────────────────────────────────
DOCS = {
    "pizza": [
        {
            "doc_id": "menu", "title": "메뉴", "category": "menu", "source_uri": "menu.pdf",
            "text": (
                "마르게리따 피자 L 25000원 토마토소스 모짜렐라 바질\n"
                "페퍼로니 피자 L 27000원 페퍼로니 추가 가능\n"
                "고르곤졸라 피자 L 28000원 꿀 포함\n"
                "콤비네이션 세트 32000원 피자L+콜라1.25L\n"
                "사이드 감자튀김 6000원 / 콜라 1.25L 3000원"
            ),
        },
        {
            "doc_id": "policy", "title": "배달 정책", "category": "policy", "source_uri": "policy.pdf",
            "text": (
                "배달 지역은 강남구와 서초구입니다\n"
                "최소주문금액은 15000원이며 배달비는 3000원입니다\n"
                "환불은 조리 시작 전까지 가능합니다"
            ),
        },
    ],
    "chinese": [
        {
            "doc_id": "menu", "title": "메뉴", "category": "menu", "source_uri": "menu.pdf",
            "text": (
                "짜장면 7000원\n짬뽕 8000원 해물 가득\n탕수육 소 18000원 대 25000원\n"
                "점심특선 짜장면+탕수육 12000원 평일 한정\n볶음밥 8000원"
            ),
        },
        {
            "doc_id": "policy", "title": "배달 정책", "category": "policy", "source_uri": "policy.pdf",
            "text": (
                "배달 지역은 마포구와 서대문구입니다\n"
                "최소주문금액은 12000원이며 배달비는 2000원입니다"
            ),
        },
    ],
    "chicken": [
        {
            "doc_id": "menu", "title": "메뉴", "category": "menu", "source_uri": "menu.pdf",
            "text": (
                "후라이드 치킨 18000원 바삭함\n양념 치킨 19000원 매콤달콤\n"
                "반반 치킨 19000원 후라이드+양념\n부분육 순살 21000원\n치즈볼 6000원"
            ),
        },
        {
            "doc_id": "policy", "title": "배달 정책", "category": "policy", "source_uri": "policy.pdf",
            "text": (
                "배달 지역은 송파구와 강동구입니다\n"
                "최소주문금액은 16000원이며 배달비는 3500원입니다"
            ),
        },
    ],
}

# ── 정형 FAQ (즉답 인터셉트용) ─────────────────────────────────────────
FAQ = {
    "pizza": [
        {"question": "영업시간이 어떻게 되나요?", "answer": "매일 11시부터 22시까지 영업합니다. (브레이크타임 15~17시)", "category": "운영"},
        {"question": "주차 가능한가요?", "answer": "건물 지하 주차장을 2시간 무료로 이용하실 수 있어요.", "category": "운영"},
    ],
    "chinese": [
        {"question": "영업시간이 어떻게 되나요?", "answer": "매일 10시 30분부터 21시 30분까지 영업합니다.", "category": "운영"},
        {"question": "점심특선은 언제 하나요?", "answer": "점심특선은 평일 11시부터 15시까지 제공됩니다.", "category": "운영"},
    ],
    "chicken": [
        {"question": "영업시간이 어떻게 되나요?", "answer": "매일 15시부터 다음날 02시까지 영업합니다.", "category": "운영"},
        {"question": "반반 주문 되나요?", "answer": "네, 반반(후라이드+양념) 주문 가능합니다. 전화 주문을 권장해요.", "category": "메뉴"},
    ],
}


async def _reset() -> None:
    """멱등 시드 — 관련 벡터 컬렉션·자동완성 풀·FAQ 이력을 초기화(재실행 시 중복 방지)."""
    client = vector_store.get_client()
    collections = ["documents", "autocomplete_q", "tools"]
    for cid in DOCS:
        collections.append(tenant_router.resolve(cid).faq.collection)  # faq_<id>
    for coll in collections:
        if await client.collection_exists(coll):
            await client.delete_collection(coll)
    # Redis 자동완성 풀 + Postgres FAQ 이력 초기화
    r = redis_client.get_client()
    async with (await postgres.init_pool()).connection() as conn:
        for cid in DOCS:
            await r.delete(f"ac:{cid}")
            await conn.execute("DELETE FROM faq_sources WHERE company_id=%s", (cid,))


async def main() -> None:
    await _reset()
    for company_id, docs in DOCS.items():
        tenant = tenant_router.resolve(company_id)
        stats = await pipeline.index_documents(company_id, docs)
        faq_res = await admin_service.upload_faq(tenant, FAQ[company_id])
        # FAQ 질문도 자동완성 풀에 추가(source: faq)
        await pipeline.add_to_autocomplete_pool(
            company_id, [{"text": f["question"], "source": "faq"} for f in FAQ[company_id]]
        )
        print(f"[{company_id}] docs chunks={stats['chunks']} acq={stats['questions']} faq={faq_res['accepted']}")

    # 도구는 업체별로 적재(payload.company_id) → retrieve_tools(company_id) 필터 대응.
    # 파일럿은 3개 업체가 동일 도구 세트를 보유(공용 코드 1벌)하므로 카탈로그를 업체별로 태깅 적재.
    catalog = mcp_client.catalog()
    total_tools = 0
    for company_id in DOCS:
        total_tools += await pipeline.index_tools(catalog, company_id)
    print(f"[tools] indexed {total_tools} tool entries ({len(catalog)} tools × {len(DOCS)} 업체)")

    await postgres.close_pool()
    await redis_client.close_client()
    await vector_store.close_client()
    print("seed done")


if __name__ == "__main__":
    asyncio.run(main())
