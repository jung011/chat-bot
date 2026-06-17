"""FastAPI 앱 진입점."""
from __future__ import annotations

import asyncio
import sys
from contextlib import asynccontextmanager

# Windows에서 psycopg(async)는 ProactorEventLoop를 지원하지 않으므로
# SelectorEventLoop 정책을 강제한다. 이벤트 루프가 생성되기 전에 적용돼야
# 효과가 있으므로, 직접 실행(run.py)·테스트 등 앱 모듈이 루프보다 먼저
# import되는 경로에서 동작한다. `uvicorn app.main:app` 으로 띄울 때는
# run.py 런처를 사용한다(루프 생성 전에 정책을 세팅).
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI

from app.api.v1 import admin, autocomplete, chat, feedback, health, sessions
from app.core.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import setup_logging
from app.db import postgres, redis_client
from app.retrieval import vector_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    # 클라이언트는 지연 연결(lazy). 종료 시 정리만 보장한다.
    yield
    await postgres.close_pool()
    await redis_client.close_client()
    await vector_store.close_client()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
register_exception_handlers(app)

for _router in (health, chat, autocomplete, sessions, feedback, admin):
    app.include_router(_router.router, prefix=settings.api_prefix)


@app.get("/")
async def root() -> dict:
    return {"data": {"service": settings.app_name, "docs": "/docs"}}
