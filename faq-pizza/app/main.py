"""FastAPI 앱 — FastMCP(streamable-http)를 마운트하고 /health 제공.

오케스트레이터는 http://<host>:<port>/mcp 로 표준 MCP 프로토콜 호출.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import vector_store
from app.config import settings
from app.mcp_server import mcp

# FastMCP 의 streamable-http ASGI 앱(내부적으로 /mcp 제공)
mcp_app = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 마운트된 MCP 세션 매니저 lifespan 을 부모 앱에서 구동
    async with mcp.session_manager.run():
        yield
    await vector_store.close_client()


app = FastAPI(title=f"faq-{settings.company_id}", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    try:
        await vector_store.ping()
        qd = "ok"
    except Exception:
        qd = "error"
    return {
        "data": {
            "status": "ok" if qd == "ok" else "degraded",
            "service": f"faq-{settings.company_id}",
            "qdrant": qd,
        }
    }


# /health 라우트 등록 후 마운트 → /mcp 는 마운트로, /health 는 위 라우트로 매칭
app.mount("/", mcp_app)
