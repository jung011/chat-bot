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
from app.mcp import domain_client  # noqa: E402
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
    "bunsik": [
        {
            "doc_id": "menu", "title": "메뉴", "category": "menu", "source_uri": "menu.pdf",
            "text": (
                "김밥 3500원\n참치김밥 4500원\n라면 4000원\n떡볶이 4000원\n"
                "라볶이 5500원 라면+떡볶이\n돈까스 7000원\n제육덮밥 7500원\n순대 5000원"
            ),
        },
        {
            "doc_id": "policy", "title": "배달 정책", "category": "policy", "source_uri": "policy.pdf",
            "text": (
                "배달 지역은 종로구와 중구입니다\n"
                "최소주문금액은 10000원이며 배달비는 2500원입니다"
            ),
        },
    ],
}

# ── 정형 FAQ (즉답 인터셉트용) ─────────────────────────────────────────
FAQ = {
    "pizza": [
        {"question": "영업시간이 어떻게 되나요?", "answer": "매일 11시부터 22시까지 영업합니다. (브레이크타임 15~17시)", "category": "운영"},
        {"question": "주차 가능한가요?", "answer": "건물 지하 주차장을 2시간 무료로 이용하실 수 있어요.", "category": "운영"},
        {"question": "포장 되나요?", "answer": "네, 모든 메뉴 포장 가능합니다.", "category": "운영"},
        {"question": "예약할 수 있나요?", "answer": "매장 예약은 전화(02-111-1111)로 가능합니다.", "category": "운영"},
        {"question": "단체 모임 되나요?", "answer": "최대 20명까지 단체석 이용 가능합니다.", "category": "운영"},
        {"question": "와이파이 되나요?", "answer": "매장 내 무료 와이파이를 제공합니다.", "category": "편의"},
        {"question": "아기 의자 있나요?", "answer": "유아용 의자를 비치하고 있습니다.", "category": "편의"},
        {"question": "콜키지 되나요?", "answer": "와인 콜키지는 병당 1만원입니다.", "category": "편의"},
    ],
    "chinese": [
        {"question": "영업시간이 어떻게 되나요?", "answer": "매일 10시 30분부터 21시 30분까지 영업합니다.", "category": "운영"},
        {"question": "점심특선은 언제 하나요?", "answer": "점심특선은 평일 11시부터 15시까지 제공됩니다.", "category": "운영"},
    ],
    "chicken": [
        {"question": "영업시간이 어떻게 되나요?", "answer": "매일 15시부터 다음날 02시까지 영업합니다.", "category": "운영"},
        {"question": "반반 주문 되나요?", "answer": "네, 반반(후라이드+양념) 주문 가능합니다. 전화 주문을 권장해요.", "category": "메뉴"},
    ],
    "bunsik": [
        {"question": "영업시간이 어떻게 되나요?", "answer": "매일 9시부터 21시까지 영업합니다.", "category": "운영"},
        {"question": "포장 되나요?", "answer": "네, 모든 메뉴 포장 가능합니다.", "category": "운영"},
        {"question": "떡볶이 맵기 조절 되나요?", "answer": "순한맛과 보통맛 중에 선택하실 수 있어요.", "category": "메뉴"},
    ],
}


async def _reset(companies: list[str]) -> None:
    """멱등 시드 — 관련 벡터 컬렉션·자동완성 풀·FAQ 이력을 초기화(재실행 시 중복 방지).

    companies 가 전체일 때만 공유 컬렉션(documents/autocomplete_q)을 통째로 비운다.
    일부만 재시드할 땐 faq_<id> 와 해당 업체 풀/이력만 정리(다른 업체 데이터 보존).
    """
    client = vector_store.get_client()
    collections = []
    if set(companies) == set(DOCS):
        collections += ["documents", "autocomplete_q"]  # tools 는 index_tools.py 가 관리
    for cid in companies:
        collections.append(tenant_router.resolve(cid).faq.collection)  # faq_<id>
    for coll in collections:
        if await client.collection_exists(coll):
            await client.delete_collection(coll)
    # Redis 자동완성 풀 + Postgres FAQ 이력 초기화
    r = redis_client.get_client()
    async with (await postgres.init_pool()).connection() as conn:
        for cid in companies:
            await r.delete(f"ac:{cid}")
            await conn.execute("DELETE FROM faq_sources WHERE company_id=%s", (cid,))


async def main() -> None:
    # ⚠️ 적재는 벤더 서버에 위임하므로 외부 서버(faq-*, general-*)가 떠 있어야 한다.
    #    먼저 'python scripts/run_external_servers.py' 실행.
    #    인자로 업체를 주면 해당 업체만 재시드(예: python scripts/seed_demo.py pizza).
    companies = [c for c in sys.argv[1:] if c in DOCS] or list(DOCS)
    await _reset(companies)
    for company_id in companies:
        docs = DOCS[company_id]
        tenant = tenant_router.resolve(company_id)
        # 문서 적재 위임 → general 벤더 서버(ingest_documents)
        doc_res = await domain_client.call(
            tenant.general_server_url, "ingest_documents", company_id, docs=docs
        )
        # FAQ 적재 위임 → faq 벤더 서버(admin_service 가 upsert_faq 호출)
        faq_res = await admin_service.upload_faq(tenant, FAQ[company_id])
        # 자동완성은 오케스트레이터 UX 기능 — 문서에서 질문 생성(LLM)
        ac = await pipeline.generate_autocomplete(company_id, docs)
        await pipeline.add_to_autocomplete_pool(
            company_id, [{"text": f["question"], "source": "faq"} for f in FAQ[company_id]]
        )
        print(f"[{company_id}] doc_chunks={doc_res.get('chunks')} faq={faq_res['accepted']} acq={ac['questions']}")

    # 도구(tools 컬렉션)는 외부 general 서버에서 list_tools 로 디스커버리해 적재한다:
    #   → python scripts/index_tools.py
    print("[tools] 외부 서버 디스커버리로 적재 — 'python scripts/index_tools.py' 실행")

    await postgres.close_pool()
    await redis_client.close_client()
    await vector_store.close_client()
    print("seed done")


if __name__ == "__main__":
    asyncio.run(main())
