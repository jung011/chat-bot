"""업체 자체 DB (PostgreSQL) — 메뉴·매장·배달지역·주문.

업체가 운용하는 RDB 를 표현한다. 오케스트레이터의 메타DB(app)와 분리된 **업체 전용
데이터베이스(pizza_shop)** 를 사용한다(같은 Postgres 인스턴스, 다른 DB). 비즈니스
데이터의 단일 진실 공급원(SSOT) — MCP 일반 서버는 이 DB 가 아니라 백엔드 API 를 호출한다.
"""
from __future__ import annotations

import os

import psycopg
from psycopg.rows import dict_row

CONNINFO = (
    f"host={os.getenv('PG_HOST', 'localhost')} "
    f"port={os.getenv('PG_PORT', '5432')} "
    f"user={os.getenv('PG_USER', 'postgres')} "
    f"password={os.getenv('PG_PASSWORD', 'postgres')} "
    f"dbname={os.getenv('PG_DB', 'pizza_shop')}"
)


def get_conn() -> psycopg.Connection:
    return psycopg.connect(CONNINFO, row_factory=dict_row)


MENU = [
    ("마르게리따 피자", 25000, "menu", "토마토소스, 모짜렐라, 바질 (L)"),
    ("페퍼로니 피자", 27000, "menu", "페퍼로니 추가 가능 (L)"),
    ("고르곤졸라 피자", 28000, "menu", "꿀 포함 (L)"),
    ("콤비네이션 세트", 32000, "set", "피자 L + 콜라 1.25L"),
    ("감자튀김", 6000, "side", ""),
    ("콜라 1.25L", 3000, "side", ""),
]

DELIVERY = [
    ("강남구", 3000, 15000, 30),
    ("서초구", 3000, 15000, 35),
]

# 라이브성 데이터(자주 변함) — RAG 로는 부적합, DB 조회가 정답인 대표 예
ORDERS = [
    ("1001", "마르게리따 피자 x1, 콜라 1.25L x1", "조리중", 25, "강남구 역삼동"),
    ("1002", "콤비네이션 세트 x2", "배달중", 10, "서초구 서초동"),
    ("1003", "페퍼로니 피자 x1", "배달완료", 0, "강남구 논현동"),
]


def init_and_seed() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS menu(
                name TEXT PRIMARY KEY, price INTEGER, category TEXT, options TEXT);
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS delivery_area(
                area TEXT PRIMARY KEY, fee INTEGER, min_order INTEGER, eta_min INTEGER);
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders(
                order_id TEXT PRIMARY KEY, items TEXT, status TEXT, eta_min INTEGER, address TEXT);
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS store(
                id INTEGER PRIMARY KEY CHECK (id = 1),
                hours TEXT, breaktime TEXT, phone TEXT, address TEXT, parking TEXT,
                order_channels TEXT, payment_methods TEXT);
            """
        )
        conn.cursor().executemany(
            "INSERT INTO menu VALUES (%s,%s,%s,%s) ON CONFLICT (name) DO UPDATE SET "
            "price=EXCLUDED.price, category=EXCLUDED.category, options=EXCLUDED.options",
            MENU,
        )
        conn.cursor().executemany(
            "INSERT INTO delivery_area VALUES (%s,%s,%s,%s) ON CONFLICT (area) DO UPDATE SET "
            "fee=EXCLUDED.fee, min_order=EXCLUDED.min_order, eta_min=EXCLUDED.eta_min",
            DELIVERY,
        )
        conn.cursor().executemany(
            "INSERT INTO orders VALUES (%s,%s,%s,%s,%s) ON CONFLICT (order_id) DO UPDATE SET "
            "items=EXCLUDED.items, status=EXCLUDED.status, eta_min=EXCLUDED.eta_min, address=EXCLUDED.address",
            ORDERS,
        )
        conn.execute(
            "INSERT INTO store VALUES (1,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (id) DO UPDATE SET "
            "hours=EXCLUDED.hours, breaktime=EXCLUDED.breaktime, phone=EXCLUDED.phone, "
            "address=EXCLUDED.address, parking=EXCLUDED.parking, "
            "order_channels=EXCLUDED.order_channels, payment_methods=EXCLUDED.payment_methods",
            (
                "매일 11:00~22:00", "15:00~17:00", "02-111-1111",
                "서울시 강남구 피자로 1", "건물 지하 주차장 2시간 무료",
                "전화, 매장방문, 배달앱", "현금, 카드, 간편결제",
            ),
        )
        conn.commit()
