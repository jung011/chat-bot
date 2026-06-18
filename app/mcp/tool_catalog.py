"""도구 카탈로그 — 오케스트레이터가 아는 외부 MCP 서버 도구 목록 (Tool RAG 인덱싱용).

도구 구현은 외부 일반 서버 프로젝트(general-*)에 있다. 오케스트레이터는 어떤 도구가
있는지(이름·설명·파라미터)만 알면 Tool RAG 로 후보를 고르고 domain_client 로 호출한다.
운영에선 각 서버의 MCP list_tools 로 동적 디스커버리할 수 있으나, 파일럿은 정적 카탈로그를 둔다.
"""
from __future__ import annotations

_COMPANY = {"company_id": {"type": "string"}}
_QUERY = {
    "type": "object",
    "properties": {**_COMPANY, "query": {"type": "string"}},
    "required": ["company_id", "query"],
}
_ONLY_COMPANY = {"type": "object", "properties": _COMPANY, "required": ["company_id"]}

CATALOG: list[dict] = [
    {"server": "documents", "name": "search_menu",
     "description": "메뉴 이름·가격·옵션·세트 구성을 검색한다. 메뉴·가격·메뉴구성·추천 문의에 사용.",
     "params_schema": _QUERY},
    {"server": "documents", "name": "search_policy",
     "description": "배달지역·배달비·최소주문금액·환불 등 정책을 검색한다. 정책·규정 문의에 사용.",
     "params_schema": _QUERY},
    {"server": "store", "name": "get_business_hours",
     "description": "영업시간·브레이크타임·휴무일을 조회한다. 영업시간·운영시간·휴무 문의에 사용.",
     "params_schema": _ONLY_COMPANY},
    {"server": "store", "name": "get_store_info",
     "description": "매장 위치·주차·전화번호 등 기본 정보를 조회한다. 위치·주소·연락처·주차 문의에 사용.",
     "params_schema": _ONLY_COMPANY},
    {"server": "store", "name": "check_delivery_area",
     "description": "특정 주소가 배달 가능 지역인지 확인한다. 배달/배송 가능 여부, 배달비, 최소주문 문의에 사용.",
     "params_schema": {"type": "object", "properties": {**_COMPANY, "address": {"type": "string"}},
                       "required": ["company_id", "address"]}},
    {"server": "order", "name": "get_order_guide",
     "description": "주문 방법·결제수단을 안내한다. 주문 방법·결제수단·주문 채널 문의에 사용.",
     "params_schema": _ONLY_COMPANY},
    {"server": "order", "name": "estimate_delivery_time",
     "description": "예상 배달 소요시간을 안내한다. 배달 시간·얼마나 걸리는지 문의에 사용.",
     "params_schema": {"type": "object", "properties": {**_COMPANY, "area": {"type": "string"}},
                       "required": ["company_id"]}},
]


def catalog() -> list[dict]:
    return list(CATALOG)
