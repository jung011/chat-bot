"""구조화 시드 데이터 (피자집 전용). store/order 도구가 사용.

이 서버는 피자집만 담당하므로 피자집 데이터만 보유한다(벤더 독립).
운영에선 업체 DB/관리 콘솔로 대체.
"""
from __future__ import annotations

STORE: dict = {
    "hours": [{"day": "매일", "open": "11:00", "close": "22:00"}],
    "breaktime": "15:00~17:00",
    "holidays": [],
    "address": "서울시 강남구 피자로 1",
    "phone": "02-111-1111",
    "parking": "건물 지하 주차 2시간 무료",
    "map_url": "https://maps.example.com/pizza",
    "delivery_areas": {
        "강남구": {"fee": 3000, "min_order": 15000, "eta_min": 35},
        "서초구": {"fee": 4000, "min_order": 18000, "eta_min": 45},
    },
    "order": {
        "channels": ["전화", "매장 방문", "배달앱"],
        "payment_methods": ["현금", "카드", "간편결제"],
        "notes": "배달앱 주문 시 쿠폰 적용 가능",
    },
}

COMPANY_ID = "pizza"


def get_store(company_id: str) -> dict | None:
    return STORE if company_id == COMPANY_ID else None
