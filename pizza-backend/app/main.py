"""피자집 백엔드 API (FastAPI + SQLite).

업체가 웹/앱 서비스를 위해 운용하는 일반적인 백엔드를 표현한다. 비즈니스 데이터
(메뉴·가격·매장·배달·주문)의 단일 진실 공급원(SSOT)이며, MCP 일반 서버는 이 API 를
호출해 데이터를 가져온다(DB 직접 접근 대신 — 로직/검증/권한 재사용).
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_and_seed()
    yield


app = FastAPI(title="pizza-backend", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok", "service": "pizza-backend"}


@app.get("/menu")
def search_menu(query: str | None = None, category: str | None = None):
    conn = db.get_conn()
    sql, params = "SELECT name, price, category, options FROM menu", []
    where = []
    if query:
        where.append("name LIKE %s")
        params.append(f"%{query}%")
    if category:
        where.append("category = %s")
        params.append(category)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY price"
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return {"items": [dict(r) for r in rows]}


@app.get("/store")
def get_store():
    conn = db.get_conn()
    r = conn.execute("SELECT * FROM store WHERE id=1").fetchone()
    conn.close()
    return dict(r) if r else {}


@app.get("/delivery/check")
def check_delivery(address: str):
    conn = db.get_conn()
    rows = conn.execute("SELECT area, fee, min_order, eta_min FROM delivery_area").fetchall()
    conn.close()
    for r in rows:
        if r["area"] in address:
            return {"deliverable": True, **dict(r)}
    return {"deliverable": False}


@app.get("/delivery/estimate")
def estimate_delivery(area: str | None = None):
    conn = db.get_conn()
    rows = conn.execute("SELECT area, eta_min FROM delivery_area").fetchall()
    conn.close()
    if area:
        for r in rows:
            if r["area"] in area:
                return {"area": r["area"], "eta_min": r["eta_min"]}
    if not rows:
        return {"eta_min": None}
    return {"eta_min": round(sum(r["eta_min"] for r in rows) / len(rows))}


@app.get("/orders/{order_id}")
def get_order(order_id: str):
    conn = db.get_conn()
    r = conn.execute(
        "SELECT order_id, items, status, eta_min, address FROM orders WHERE order_id=%s",
        (order_id,),
    ).fetchone()
    conn.close()
    if not r:
        return {"found": False}
    return {"found": True, **dict(r)}
