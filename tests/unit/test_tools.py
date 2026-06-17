from mcp_servers._shared.responses import fail, ok
from mcp_servers.domains.order.tools import estimate_delivery_time, get_order_guide
from mcp_servers.domains.store.tools import check_delivery_area, get_business_hours


def test_response_helpers():
    assert ok(a=1) == {"success": True, "a": 1}
    assert fail("x") == {"success": False, "message": "x"}


async def test_business_hours_ok():
    r = await get_business_hours("pizza")
    assert r["success"] and r["hours"]


async def test_business_hours_unknown_company():
    r = await get_business_hours("ghost")
    assert r["success"] is False


async def test_delivery_area_match_and_miss():
    deliverable = await check_delivery_area("chicken", "서울시 송파구 어딘가")
    assert deliverable["success"] and deliverable["deliverable"] is True
    miss = await check_delivery_area("chicken", "부산광역시")
    assert miss["success"] and miss["deliverable"] is False


async def test_delivery_area_requires_address():
    r = await check_delivery_area("pizza", "")
    assert r["success"] is False


async def test_order_tools():
    g = await get_order_guide("chinese")
    assert g["success"] and "channels" in g
    e = await estimate_delivery_time("pizza", area="강남구")
    assert e["success"] and e["eta_min"] > 0
