"""구조화 시드 데이터 (중국집 전용). store/order 도구가 사용."""
from __future__ import annotations

STORE: dict = {
    "hours": [{"day": "매일", "open": "10:30", "close": "21:30"}],
    "breaktime": None,
    "holidays": [],
    "address": "서울시 마포구 중화로 22",
    "phone": "02-222-2222",
    "parking": "인근 공영주차장 이용",
    "map_url": "https://maps.example.com/chinese",
    "delivery_areas": {
        "마포구": {"fee": 2000, "min_order": 12000, "eta_min": 30},
        "서대문구": {"fee": 3000, "min_order": 15000, "eta_min": 40},
    },
    "order": {
        "channels": ["전화", "매장 방문", "배달앱"],
        "payment_methods": ["현금", "카드"],
        "notes": "점심특선은 평일 11:00~15:00 한정",
    },
}

COMPANY_ID = "chinese"


def get_store(company_id: str) -> dict | None:
    return STORE if company_id == COMPANY_ID else None
