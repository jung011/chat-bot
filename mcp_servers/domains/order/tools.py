"""order 서버 도구 (§08 §4.3, §5.4) — 안내용.

주문 방법/결제수단 안내, 예상 배달시간 산출. 실제 주문/결제 처리는 범위 밖(§05).
"""
from __future__ import annotations

from mcp_servers._shared.responses import fail, ok
from mcp_servers._shared.seed_data import get_store
from mcp_servers._shared.tooling import ToolSpec

_COMPANY = {"company_id": {"type": "string"}}


async def get_order_guide(company_id: str) -> dict:
    """주문 방법·결제수단을 안내한다. 주문/결제 방법 문의에 사용."""
    store = get_store(company_id)
    if not store:
        return fail("주문 안내 정보가 등록되지 않았습니다.")
    o = store["order"]
    return ok(
        channels=o["channels"],
        payment_methods=o["payment_methods"],
        notes=o.get("notes"),
    )


async def estimate_delivery_time(company_id: str, area: str | None = None) -> dict:
    """예상 배달 소요시간을 안내한다. 배달 시간 문의에 사용."""
    store = get_store(company_id)
    if not store:
        return fail("배달 시간 정보를 산출할 수 없습니다.")
    areas = store.get("delivery_areas", {})
    if area:
        for name, info in areas.items():
            if name in area:
                return ok(eta_min=info["eta_min"], area=name, peak=False)
    # 지역 미지정/미매칭 → 전체 평균
    if not areas:
        return fail("배달 시간 정보를 산출할 수 없습니다.")
    avg = round(sum(i["eta_min"] for i in areas.values()) / len(areas))
    return ok(eta_min=avg, peak=False)


TOOLS: list[ToolSpec] = [
    ToolSpec(
        server="order",
        name="get_order_guide",
        description="주문 방법·결제수단을 안내한다. 주문 방법·결제수단·주문 채널 문의에 사용.",
        params_schema={"type": "object", "properties": _COMPANY, "required": ["company_id"]},
        handler=get_order_guide,
    ),
    ToolSpec(
        server="order",
        name="estimate_delivery_time",
        description="예상 배달 소요시간을 안내한다. 배달 시간·얼마나 걸리는지 문의에 사용.",
        params_schema={
            "type": "object",
            "properties": {**_COMPANY, "area": {"type": "string"}},
            "required": ["company_id"],
        },
        handler=estimate_delivery_time,
    ),
]
