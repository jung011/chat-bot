"""pytest 공통 설정.

Windows 에서 psycopg(async)는 ProactorEventLoop 를 못 쓰므로, 이벤트 루프가
생성되기 전(=이 모듈 import 시점)에 SelectorEventLoop 정책을 강제한다.
통합 테스트는 로컬 도커 DB(Postgres/Redis/Qdrant)와 시드 데이터가 필요하다.
"""
from __future__ import annotations

import asyncio
import sys

import pytest

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(autouse=True)
def _reset_db_singletons():
    """pytest-asyncio 는 테스트마다 새 이벤트 루프를 만든다. 전역 캐싱된 DB
    클라이언트(이전 루프에 바인딩)를 리셋해 'Event loop is closed' 를 방지한다.
    (각 테스트가 자기 루프에서 클라이언트를 새로 생성하도록.)"""
    from app.db import postgres, redis_client
    from app.retrieval import vector_store

    postgres._pool = None
    redis_client._client = None
    vector_store._client = None
    yield

