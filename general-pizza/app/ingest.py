"""문서 적재 — 이 서버가 자기 업체 문서를 소유·관리한다(벤더 적재).

문서를 청킹→자체 임베더로 임베딩→공유 Qdrant `documents` 컬렉션에 적재(company_id 태깅).
결정적 ID 로 멱등. 오케스트레이터가 ingest_documents 도구로 위임 호출(데이터 소유=벤더).
"""
from __future__ import annotations

from app.chunking import chunk
from app.config import settings
from app.embedder import get_embedder
from app.vector_store import ensure_collection, upsert

DOCUMENTS_COLLECTION = "documents"


async def ingest_documents(docs: list[dict]) -> dict:
    """docs: [{doc_id, title, category, text, source_uri}] → 청크 적재. {chunks} 반환."""
    await ensure_collection(DOCUMENTS_COLLECTION, settings.embedding_dim)
    points = []
    for doc in docs:
        for idx, ch in enumerate(chunk(doc.get("text", ""))):
            points.append(
                {
                    "id": f"{settings.company_id}_{doc['doc_id']}_{idx}",
                    "vector": get_embedder().embed(ch),
                    "payload": {
                        "company_id": settings.company_id,
                        "doc_id": doc["doc_id"],
                        "chunk_index": idx,
                        "text": ch,
                        "title": doc.get("title", ""),
                        "category": doc.get("category", ""),
                        "source_uri": doc.get("source_uri", ""),
                    },
                }
            )
    n = await upsert(DOCUMENTS_COLLECTION, points)
    return {"chunks": n}
