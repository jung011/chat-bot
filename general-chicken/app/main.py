"""FastAPI 앱 — FastMCP(streamable-http) 마운트 + /health."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import vector_store
from app.config import settings
from app.mcp_server import mcp

mcp_app = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with mcp.session_manager.run():
        yield
    await vector_store.close_client()


app = FastAPI(title=f"general-{settings.company_id}", lifespan=lifespan)


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
            "service": f"general-{settings.company_id}",
            "qdrant": qd,
        }
    }


app.mount("/", mcp_app)
