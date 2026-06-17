"""PostgreSQL 비동기 연결 풀 (기존 로컬 도커 컨테이너 연결)."""
from __future__ import annotations

from psycopg_pool import AsyncConnectionPool

from app.core.config import settings

_pool: AsyncConnectionPool | None = None


async def init_pool() -> AsyncConnectionPool:
    """풀을 지연 생성·오픈한다 (DB 미가동 시에도 앱은 기동되도록 lazy)."""
    global _pool
    if _pool is None:
        _pool = AsyncConnectionPool(
            conninfo=settings.postgres_dsn, min_size=1, max_size=10, open=False
        )
    if _pool.closed:
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
