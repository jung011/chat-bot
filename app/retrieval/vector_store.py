"""Qdrant 벡터 스토어 클라이언트 (기존 로컬 도커 컨테이너 연결).

문서 02 §retrieval, 04 §3 참고. 파일럿은 단일 Qdrant 인스턴스에
업체별 컬렉션(faq_<company_id> 등)으로 시작한다.
(법적 격리 A안의 '업체별 인스턴스 분리'는 추후 전환 — 04 §7 결정사항)

컬렉션(§04 §3.1): faq_<company_id> / documents / tools / autocomplete_q
모든 검색/조회에 company_id 필터를 강제한다(§04 §2).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from qdrant_client import AsyncQdrantClient, models

from app.core.config import settings
from app.retrieval.embedder import get_embedder

# Qdrant 포인트 ID 는 unsigned int 또는 UUID 만 허용. 우리는 의미있는 문자열
# ID(예: faq_pizza_..)를 쓰므로 결정적 UUID5 로 변환한다(재적재 시 동일 ID 로 덮어쓰기).
_ID_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000abc")

_client: AsyncQdrantClient | None = None


def _point_id(raw: Any) -> str | int:
    if isinstance(raw, int):
        return raw
    return str(uuid.uuid5(_ID_NAMESPACE, str(raw)))


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
    id: str | int
    score: float
    payload: dict[str, Any]


async def ensure_collection(name: str) -> None:
    """컬렉션이 없으면 생성(코사인 거리, embedding_dim)."""
    client = get_client()
    if not await client.collection_exists(name):
        await client.create_collection(
            collection_name=name,
            vectors_config=models.VectorParams(
                size=settings.embedding_dim, distance=models.Distance.COSINE
            ),
        )


async def upsert(name: str, points: list[dict[str, Any]]) -> int:
    """points: [{id, vector, payload}] 적재. 적재 건수 반환."""
    if not points:
        return 0
    client = get_client()
    await client.upsert(
        collection_name=name,
        points=[
            models.PointStruct(id=_point_id(p["id"]), vector=p["vector"], payload=p["payload"])
            for p in points
        ],
    )
    return len(points)


def _company_filter(company_id: str | None) -> models.Filter | None:
    if not company_id:
        return None
    return models.Filter(
        must=[
            models.FieldCondition(
                key="company_id", match=models.MatchValue(value=company_id)
            )
        ]
    )


async def search(
    name: str,
    query: str,
    *,
    company_id: str | None = None,
    top_k: int = 10,
    score_threshold: float | None = None,
) -> list[Hit]:
    """질의 임베딩 → 벡터 검색. company_id 가 주어지면 페이로드 필터 강제."""
    client = get_client()
    if not await client.collection_exists(name):
        return []
    vector = get_embedder().embed(query)
    res = await client.query_points(
        collection_name=name,
        query=vector,
        limit=top_k,
        query_filter=_company_filter(company_id),
        score_threshold=score_threshold,
        with_payload=True,
    )
    return [Hit(id=p.id, score=p.score, payload=p.payload or {}) for p in res.points]
