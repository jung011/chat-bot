"""Redis 비동기 클라이언트 (기존 로컬 도커 컨테이너 연결)."""
from __future__ import annotations

import redis.asyncio as aioredis

from app.core.config import settings

_client: "aioredis.Redis | None" = None


def get_client() -> "aioredis.Redis":
    global _client
    if _client is None:
        _client = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
    _client = None


async def ping() -> bool:
    return bool(await get_client().ping())
