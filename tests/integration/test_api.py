"""통합 테스트 — 로컬 도커 DB + 시드 데이터 필요(scripts/seed_demo.py 선실행).

httpx ASGITransport 로 인메모리 호출(서버 기동 불필요). DB 미가동 시 실패한다.
"""
from __future__ import annotations

import urllib.request

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app

BASE = "http://test"
FAQ_SERVER = "http://127.0.0.1:9001/health"  # faq-pizza 외부 서버


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url=BASE)


def _faq_server_up() -> bool:
    try:
        urllib.request.urlopen(FAQ_SERVER, timeout=1)
        return True
    except Exception:
        return False


async def test_health():
    async with _client() as c:
        r = await c.get("/v1/health")
    assert r.status_code == 200
    deps = r.json()["data"]["dependencies"]
    assert deps["postgres"] == "ok" and deps["vector_db"] == "ok" and deps["redis"] == "ok"


async def test_invalid_company_id():
    async with _client() as c:
        r = await c.post("/v1/chat/sync", json={"company_id": "ghost", "message": "안녕"})
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "INVALID_REQUEST"


async def test_chat_sync_faq_intercept():
    """정형 FAQ 질문 → faq_intercept 경로. 외부 faq 서버 필요(원격 전용)."""
    if not _faq_server_up():
        pytest.skip("faq 외부 서버(9001) 미가동 — run_external_servers.py 필요")
    async with _client() as c:
        r = await c.post(
            "/v1/chat/sync",
            json={"company_id": "pizza", "message": "영업시간이 어떻게 되나요?"},
        )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["route"] == "faq_intercept"
    assert "11" in data["answer"]  # 11시~22시
    assert data["sources"] and data["sources"][0]["type"] == "faq"


async def test_chat_sync_rag_retrieves_documents():
    """메뉴 질문 → rag 경로, 문서 근거가 붙는다(생성은 키 없으면 폴백)."""
    async with _client() as c:
        r = await c.post(
            "/v1/chat/sync",
            json={"company_id": "pizza", "message": "마르게리따 피자 가격 알려줘"},
        )
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["route"] in ("rag", "agent")


async def test_autocomplete_tenant_isolation():
    async with _client() as c:
        r = await c.get("/v1/autocomplete", params={"company_id": "pizza", "q": "영업"})
    assert r.status_code == 200
    assert r.json()["data"]["query"] == "영업"


async def test_session_lifecycle():
    async with _client() as c:
        created = await c.post("/v1/sessions", json={"company_id": "pizza", "title": "t"})
        assert created.status_code == 201
        sid = created.json()["data"]["session_id"]

        listed = await c.get("/v1/sessions", params={"company_id": "pizza"})
        assert any(s["session_id"] == sid for s in listed.json()["data"])

        deleted = await c.delete(f"/v1/sessions/{sid}", params={"company_id": "pizza"})
        assert deleted.json()["data"]["deleted"] is True


async def test_cross_tenant_session_not_found():
    async with _client() as c:
        created = await c.post("/v1/sessions", json={"company_id": "pizza"})
        sid = created.json()["data"]["session_id"]
        # 다른 테넌트로 조회 → 404
        r = await c.get(f"/v1/sessions/{sid}/messages", params={"company_id": "chinese"})
    assert r.status_code == 404


async def test_admin_requires_token():
    async with _client() as c:
        r = await c.post("/v1/admin/index", json={"company_id": "pizza", "source": "documents"})
    assert r.status_code == 401
