"""헬스체크 엔드포인트 (인증 불필요 — 문서 03 §3.7)."""
from __future__ import annotations

from typing import Awaitable

from fastapi import APIRouter

from app.db import postgres, redis_client
from app.llm.client import get_llm
from app.retrieval import vector_store

router = APIRouter()


async def _safe(coro: Awaitable[bool]) -> str:
    try:
        await coro
        return "ok"
    except Exception:
        return "error"


@router.get("/health")
async def health() -> dict:
    deps = {
        "postgres": await _safe(postgres.ping()),
        "redis": await _safe(redis_client.ping()),
        "vector_db": await _safe(vector_store.ping()),
        # LLM 은 키 설정 여부만 보고(외부 호출 없이). 미설정이면 키 없이도
        # FAQ/검색은 동작하므로 전체 status 는 degraded 로만 표시한다.
        "llm": "ok" if get_llm().available else "not_configured",
    }
    core_ok = all(deps[k] == "ok" for k in ("postgres", "redis", "vector_db"))
    status = "ok" if core_ok and deps["llm"] == "ok" else "degraded"
    return {"data": {"status": status, "dependencies": deps}}
