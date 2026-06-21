"""구조화 시드 데이터 (분식집 전용). store/order 도구가 사용."""
from __future__ import annotations

STORE: dict = {
    "hours": [{"day": "매일", "open": "09:00", "close": "21:00"}],
    "breaktime": None,
    "holidays": [],
    "address": "서울시 종로구 분식로 5",
    "phone": "02-444-4444",
    "parking": "주차 불가(인근 공영주차장)",
    "map_url": "https://maps.example.com/bunsik",
    "delivery_areas": {
        "종로구": {"fee": 2500, "min_order": 10000, "eta_min": 25},
        "중구": {"fee": 3000, "min_order": 12000, "eta_min": 35},
    },
    "order": {
        "channels": ["전화", "매장 방문", "배달앱"],
        "payment_methods": ["현금", "카드", "간편결제"],
        "notes": "떡볶이 맵기 조절 가능(순한맛/보통/매운맛)",
    },
}

COMPANY_ID = "bunsik"


def get_store(company_id: str) -> dict | None:
    return STORE if company_id == COMPANY_ID else None
