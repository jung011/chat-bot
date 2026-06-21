"""구조화 시드 데이터 (치킨집 전용). store/order 도구가 사용."""
from __future__ import annotations

STORE: dict = {
    "hours": [{"day": "매일", "open": "15:00", "close": "02:00"}],
    "breaktime": None,
    "holidays": [],
    "address": "서울시 송파구 치킨대로 33",
    "phone": "02-333-3333",
    "parking": "주차 불가(인근 노상)",
    "map_url": "https://maps.example.com/chicken",
    "delivery_areas": {
        "송파구": {"fee": 3500, "min_order": 16000, "eta_min": 40},
        "강동구": {"fee": 4500, "min_order": 18000, "eta_min": 50},
    },
    "order": {
        "channels": ["전화", "배달앱"],
        "payment_methods": ["현금", "카드", "간편결제"],
        "notes": "반반/부분육 주문은 전화 권장",
    },
}

COMPANY_ID = "chicken"


def get_store(company_id: str) -> dict | None:
    return STORE if company_id == COMPANY_ID else None
