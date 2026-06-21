"""FastMCP 서버 — 도메인 도구.

데이터 성격별로 백엔드를 나눈다:
- **정형/실시간 데이터**(메뉴·가격·매장·배달·주문) → 업체 **백엔드 API**(backend_client) 호출.
  DB 직접 접근 대신 API 를 타서 비즈니스 로직/검증/권한을 재사용한다(데이터 소유=백엔드 DB).
- **비정형 텍스트**(정책 설명 등) → 공유 Qdrant `documents` 벡터검색(RAG).
모든 도구는 company_id 인자를 받아 격리. (이름·반환 형식은 연동 계약 §08 §9.2 고정)
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app import backend_client, ingest, search
from app.config import settings
from app.responses import fail, ok

mcp = FastMCP(f"general-{settings.company_id}")


@mcp.tool()
async def ingest_documents(company_id: str, docs: list[dict]) -> dict:
    """업체 비정형 문서를 적재(청킹→임베딩→documents 컬렉션). docs: [{doc_id,title,category,text,source_uri}]."""
    return await ingest.ingest_documents(docs)


# ── 정형/실시간 데이터: 백엔드 API 호출(DB 소유=백엔드) ────────────────
@mcp.tool()
async def search_menu(company_id: str, query: str) -> dict:
    """메뉴 이름·가격·옵션·세트 구성을 조회한다. 메뉴/가격/구성 문의에 사용."""
    if not query or not query.strip():
        return fail("검색어를 입력해 주세요.")
    data = await backend_client.get("/menu", {"query": query})
    items = (data or {}).get("items", [])
    if not items:
        return fail("관련 메뉴를 찾지 못했습니다.")
    return ok(items=items, count=len(items))


@mcp.tool()
async def get_business_hours(company_id: str) -> dict:
    """영업시간·브레이크타임을 조회한다. 영업시간 문의에 사용."""
    s = await backend_client.get("/store")
    if not s:
        return fail("영업시간 정보를 조회하지 못했습니다.")
    return ok(hours=s.get("hours"), breaktime=s.get("breaktime"))


@mcp.tool()
async def get_store_info(company_id: str) -> dict:
    """매장 위치·주차·전화번호 등 기본 정보를 조회한다. 위치/연락처 문의에 사용."""
    s = await backend_client.get("/store")
    if not s:
        return fail("매장 정보를 조회하지 못했습니다.")
    return ok(address=s.get("address"), phone=s.get("phone"), parking=s.get("parking"))


@mcp.tool()
async def check_delivery_area(company_id: str, address: str) -> dict:
    """특정 주소가 배달 가능 지역인지 확인한다. 배달 가능 여부 문의에 사용."""
    if not address or not address.strip():
        return fail("확인할 주소를 입력해 주세요.")
    data = await backend_client.get("/delivery/check", {"address": address})
    if not data:
        return fail("배달 지역 정보를 조회하지 못했습니다.")
    if not data.get("deliverable"):
        return ok(deliverable=False, message="입력하신 주소는 현재 배달 가능 지역이 아니에요.")
    return ok(deliverable=True, area=data["area"], fee=data["fee"],
              min_order=data["min_order"], eta_min=data["eta_min"])


@mcp.tool()
async def estimate_delivery_time(company_id: str, area: str | None = None) -> dict:
    """예상 배달 소요시간을 안내한다. 배달 시간 문의에 사용."""
    data = await backend_client.get("/delivery/estimate", {"area": area} if area else None)
    if not data or data.get("eta_min") is None:
        return fail("배달 시간 정보를 산출하지 못했습니다.")
    return ok(eta_min=data["eta_min"], area=data.get("area"))


@mcp.tool()
async def get_order_guide(company_id: str) -> dict:
    """주문 방법·결제수단을 안내한다. 주문/결제 방법 문의에 사용."""
    s = await backend_client.get("/store")
    if not s:
        return fail("주문 안내 정보를 조회하지 못했습니다.")
    return ok(channels=s.get("order_channels"), payment_methods=s.get("payment_methods"))


@mcp.tool()
async def get_order_status(company_id: str, order_id: str) -> dict:
    """주문번호로 현재 주문 상태와 예상 시간을 조회한다(라이브 DB). 주문 상태/배송 조회에 사용."""
    if not order_id or not order_id.strip():
        return fail("주문번호를 입력해 주세요.")
    data = await backend_client.get(f"/orders/{order_id.strip()}")
    if not data or not data.get("found"):
        return fail(f"주문번호 {order_id} 를 찾지 못했습니다.")
    return ok(order_id=data["order_id"], status=data["status"],
              eta_min=data["eta_min"], items=data["items"])


# ── 비정형 텍스트: RAG(벡터검색) ──────────────────────────────────────
@mcp.tool()
async def search_policy(company_id: str, query: str) -> dict:
    """배달비·최소주문·환불 등 정책 문서를 검색한다(비정형 텍스트, RAG). 정책 문의에 사용."""
    if not query or not query.strip():
        return fail("검색어를 입력해 주세요.")
    hits = await search.hybrid_rerank(query, company_id, category="policy")
    if not hits:
        return fail("관련 정책 정보를 찾지 못했습니다.")
    snippets = [{"title": h.payload.get("title"), "text": h.payload.get("text")} for h in hits]
    return ok(snippets=snippets, count=len(snippets))
