"""PostgreSQL 비동기 연결 풀 (기존 로컬 도커 컨테이너 연결)."""
from __future__ import annotations

from psycopg_pool import AsyncConnectionPool

from app.core.config import settings

_pool: AsyncConnectionPool | None = None


async def init_pool() -> AsyncConnectionPool:
    """풀을 지연 생성·오픈한다 (DB 미가동 시에도 앱은 기동되도록 lazy).

    풀이 닫힌 상태(미오픈 또는 이전 open 실패로 '오염')면 **새로 생성**한다.
    psycopg 풀은 open 실패 시 영구 재사용 불가가 되므로, 재생성으로 자동 복구한다
    (DB 가 기동 중 잠깐 끊겨도 다음 요청에서 회복)."""
    global _pool
    if _pool is None or _pool.closed:
        _pool = AsyncConnectionPool(
            conninfo=settings.postgres_dsn, min_size=1, max_size=10, open=False
        )
        await _pool.open(wait=True, timeout=5.0)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None and not _pool.closed:
        await _pool.close()
    _pool = None


async def ping() -> bool:
    pool = await init_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute("SELECT 1")
            await cur.fetchone()
    return True
