"""FastMCP 서버 — 도메인 도구 7개(documents·store·order).

documents 도구는 공유 Qdrant `documents` 컬렉션을 company_id 필터로 검색(Hybrid+Rerank).
store·order 도구는 자체 seed_data(피자집) 사용. 모든 도구는 company_id 인자를 받아 격리.
"""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app import ingest, search
from app.config import settings
from app.responses import fail, ok
from app.seed_data import get_store

mcp = FastMCP(f"general-{settings.company_id}")


@mcp.tool()
async def ingest_documents(company_id: str, docs: list[dict]) -> dict:
    """업체 문서를 적재(청킹→임베딩→documents 컬렉션). docs: [{doc_id,title,category,text,source_uri}].
    company_id 는 호출 일관성용 — 이 서버는 자기 설정(company_id)으로 적재한다."""
    return await ingest.ingest_documents(docs)


# ── documents 서버 도구 ────────────────────────────────────────────────
@mcp.tool()
async def search_menu(company_id: str, query: str) -> dict:
    """메뉴 이름·가격·옵션·세트 구성을 검색한다. 메뉴/가격/구성 문의에 사용."""
    if not query or not query.strip():
        return fail("검색어를 입력해 주세요.")
    hits = await search.hybrid_rerank(query, company_id, category="menu")
    if not hits:
        return fail("관련 메뉴를 찾지 못했습니다.")
    items = [{"text": h.payload.get("text"), "title": h.payload.get("title"), "score": round(h.score, 3)} for h in hits]
    return ok(items=items, count=len(items))


@mcp.tool()
async def search_policy(company_id: str, query: str) -> dict:
    """배달지역·배달비·최소주문금액·환불 등 정책을 검색한다. 정책 문의에 사용."""
    if not query or not query.strip():
        return fail("검색어를 입력해 주세요.")
    hits = await search.hybrid_rerank(query, company_id, category="policy")
    if not hits:
        return fail("관련 정책 정보를 찾지 못했습니다.")
    snippets = [{"title": h.payload.get("title"), "text": h.payload.get("text"), "source": h.payload.get("source_uri")} for h in hits]
    return ok(snippets=snippets, count=len(snippets))


# ── store 서버 도구 ────────────────────────────────────────────────────
@mcp.tool()
async def get_business_hours(company_id: str) -> dict:
    """영업시간·브레이크타임·휴무일을 조회한다. 영업시간 문의에 사용."""
    s = get_store(company_id)
    if not s:
        return fail("영업시간 정보가 등록되지 않았습니다.")
    return ok(hours=s["hours"], breaktime=s.get("breaktime"), holidays=s.get("holidays", []))


@mcp.tool()
async def get_store_info(company_id: str) -> dict:
    """매장 위치·주차·전화번호 등 기본 정보를 조회한다. 위치/연락처 문의에 사용."""
    s = get_store(company_id)
    if not s:
        return fail("매장 정보가 등록되지 않았습니다.")
    return ok(address=s["address"], phone=s["phone"], parking=s.get("parking"), map_url=s.get("map_url"))


@mcp.tool()
async def check_delivery_area(company_id: str, address: str) -> dict:
    """특정 주소가 배달 가능 지역인지 확인한다. 배달/배송 가능 여부 문의에 사용."""
    if not address or not address.strip():
        return fail("확인할 주소를 입력해 주세요.")
    s = get_store(company_id)
    if not s:
        return fail("해당 주소의 배달 지역 정보를 찾을 수 없습니다.")
    for area, info in s.get("delivery_areas", {}).items():
        if area in address:
            return ok(deliverable=True, area=area, fee=info["fee"], min_order=info["min_order"], eta_min=info["eta_min"])
    return ok(deliverable=False, message="입력하신 주소는 현재 배달 가능 지역이 아니에요.")


# ── order 서버 도구 ────────────────────────────────────────────────────
@mcp.tool()
async def get_order_guide(company_id: str) -> dict:
    """주문 방법·결제수단을 안내한다. 주문/결제 방법 문의에 사용."""
    s = get_store(company_id)
    if not s:
        return fail("주문 안내 정보가 등록되지 않았습니다.")
    o = s["order"]
    return ok(channels=o["channels"], payment_methods=o["payment_methods"], notes=o.get("notes"))


@mcp.tool()
async def estimate_delivery_time(company_id: str, area: str | None = None) -> dict:
    """예상 배달 소요시간을 안내한다. 배달 시간 문의에 사용."""
    s = get_store(company_id)
    if not s:
        return fail("배달 시간 정보를 산출할 수 없습니다.")
    areas = s.get("delivery_areas", {})
    if area:
        for name, info in areas.items():
            if name in area:
                return ok(eta_min=info["eta_min"], area=name, peak=False)
    if not areas:
        return fail("배달 시간 정보를 산출할 수 없습니다.")
    avg = round(sum(i["eta_min"] for i in areas.values()) / len(areas))
    return ok(eta_min=avg, peak=False)
