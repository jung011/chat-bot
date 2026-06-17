"""store 서버 도구 (§08 §4.2, §5.4).

영업시간/매장정보/배달지역 등 구조화 데이터를 조회한다. company_id 필터 필수.
"""
from __future__ import annotations

from mcp_servers._shared.responses import fail, ok
from mcp_servers._shared.seed_data import get_store
from mcp_servers._shared.tooling import ToolSpec

_COMPANY = {"company_id": {"type": "string"}}


async def get_business_hours(company_id: str) -> dict:
    """영업시간·브레이크타임·휴무일을 조회한다. 영업시간 문의에 사용."""
    store = get_store(company_id)
    if not store:
        return fail("영업시간 정보가 등록되지 않았습니다.")
    return ok(
        hours=store["hours"],
        breaktime=store.get("breaktime"),
        holidays=store.get("holidays", []),
    )


async def get_store_info(company_id: str) -> dict:
    """매장 위치·주차·전화번호 등 기본 정보를 조회한다. 위치/연락처 문의에 사용."""
    store = get_store(company_id)
    if not store:
        return fail("매장 정보가 등록되지 않았습니다.")
    return ok(
        address=store["address"],
        phone=store["phone"],
        parking=store.get("parking"),
        map_url=store.get("map_url"),
    )


async def check_delivery_area(company_id: str, address: str) -> dict:
    """특정 주소가 배달 가능 지역인지 확인한다. 배달/배송 가능 여부 문의에 사용."""
    if not address or not address.strip():
        return fail("확인할 주소를 입력해 주세요.")
    store = get_store(company_id)
    if not store:
        return fail("해당 주소의 배달 지역 정보를 찾을 수 없습니다.")
    for area, info in store.get("delivery_areas", {}).items():
        if area in address:
            return ok(
                deliverable=True,
                area=area,
                fee=info["fee"],
                min_order=info["min_order"],
                eta_min=info["eta_min"],
            )
    return ok(deliverable=False, message="입력하신 주소는 현재 배달 가능 지역이 아니에요.")


TOOLS: list[ToolSpec] = [
    ToolSpec(
        server="store",
        name="get_business_hours",
        description="영업시간·브레이크타임·휴무일을 조회한다. 영업시간·운영시간·휴무 문의에 사용.",
        params_schema={"type": "object", "properties": _COMPANY, "required": ["company_id"]},
        handler=get_business_hours,
    ),
    ToolSpec(
        server="store",
        name="get_store_info",
        description="매장 위치·주차·전화번호 등 기본 정보를 조회한다. 위치·주소·연락처·주차 문의에 사용.",
        params_schema={"type": "object", "properties": _COMPANY, "required": ["company_id"]},
        handler=get_store_info,
    ),
    ToolSpec(
        server="store",
        name="check_delivery_area",
        description="특정 주소가 배달 가능 지역인지 확인한다. 배달/배송 가능 여부, 배달비, 최소주문 문의에 사용.",
        params_schema={
            "type": "object",
            "properties": {**_COMPANY, "address": {"type": "string"}},
            "required": ["company_id", "address"],
        },
        handler=check_delivery_area,
    ),
]
