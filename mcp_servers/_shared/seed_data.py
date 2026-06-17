"""도메인 구조화 시드 데이터 (store/order 도구용).

파일럿용 인메모리 데이터. 운영에서는 업체별 DB/관리 콘솔로 대체한다.
모든 조회는 company_id 로 필터(테넌트 격리, §08 §5.2).
메뉴/정책 등 비정형 텍스트는 Qdrant `documents` 컬렉션에서 검색하므로 여기 없음.
"""
from __future__ import annotations

STORE: dict[str, dict] = {
    "pizza": {
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
    },
    "chinese": {
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
    },
    "chicken": {
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
    },
}


def get_store(company_id: str) -> dict | None:
    return STORE.get(company_id)
