"""Qdrant 벡터 검색·적재 (FAQ 전용)."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from qdrant_client import AsyncQdrantClient, models

from app.config import settings

# 의미있는 문자열 ID → 결정적 UUID5 (오케스트레이터와 동일 네임스페이스 → 재적재 시 덮어쓰기)
_ID_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000abc")

_client: AsyncQdrantClient | None = None


def _point_id(raw: Any) -> str | int:
    return raw if isinstance(raw, int) else str(uuid.uuid5(_ID_NAMESPACE, str(raw)))


def get_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(host=settings.qdrant_host, port=settings.qdrant_port)
    return _client


async def close_client() -> None:
    global _client
    if _client is not None:
        await _client.close()
    _client = None


async def ping() -> bool:
    await get_client().get_collections()
    return True


@dataclass
class Hit:
    score: float
    payload: dict


async def ensure_collection(name: str, dim: int) -> None:
    client = get_client()
    if not await client.collection_exists(name):
        await client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
        )
    try:
        await client.create_payload_index(
            collection_name=name, field_name="company_id",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
    except Exception:
        pass


async def upsert(name: str, points: list[dict[str, Any]]) -> int:
    if not points:
        return 0
    await get_client().upsert(
        collection_name=name,
        points=[
            models.PointStruct(id=_point_id(p["id"]), vector=p["vector"], payload=p["payload"])
            for p in points
        ],
    )
    return len(points)


async def search(collection: str, vector: list[float], company_id: str, top_k: int) -> list[Hit]:
    """임계값 없이 유사도 상위 K건(생성 컨텍스트용 — search_faq 도구)."""
    client = get_client()
    if not await client.collection_exists(collection):
        return []
    res = await client.query_points(
        collection_name=collection,
        query=vector,
        limit=top_k,
        query_filter=models.Filter(
            must=[models.FieldCondition(key="company_id", match=models.MatchValue(value=company_id))]
        ),
        with_payload=True,
    )
    return [Hit(score=p.score, payload=p.payload or {}) for p in res.points]


async def search_threshold(
    collection: str, vector: list[float], company_id: str, threshold: float
) -> Hit | None:
    """임계값 이상 최상위 1건. 없으면 None."""
    client = get_client()
    if not await client.collection_exists(collection):
        return None
    res = await client.query_points(
        collection_name=collection,
        query=vector,
        limit=1,
        score_threshold=threshold,
        query_filter=models.Filter(
            must=[models.FieldCondition(key="company_id", match=models.MatchValue(value=company_id))]
        ),
        with_payload=True,
    )
    if not res.points:
        return None
    p = res.points[0]
    return Hit(score=p.score, payload=p.payload or {})
