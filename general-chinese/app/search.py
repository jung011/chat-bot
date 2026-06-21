"""문서 검색 — Hybrid(벡터+BM25) + Rerank. (company_id 필터)"""
from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from app.config import settings
from app.embedder import HashEmbedder
from app.vector_store import Hit, search

_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
_embedder = HashEmbedder(settings.embedding_dim)


def _tok(t: str) -> list[str]:
    return _TOKEN_RE.findall(t.lower())


def _minmax(scores: list[float]) -> list[float]:
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi - lo < 1e-9:
        return [1.0 for _ in scores]
    return [(s - lo) / (hi - lo) for s in scores]


def _text(payload: dict) -> str:
    if payload.get("text"):
        return str(payload["text"])
    return " ".join(str(payload.get(k, "")) for k in ("title", "text"))


async def hybrid_rerank(query: str, company_id: str, category: str | None = None) -> list[Hit]:
    """Hybrid 검색(over-fetch) → BM25 블렌딩 → 어휘 커버리지 Rerank → Top-N."""
    candidates = await search(
        settings.documents_collection, _embedder.embed(query), company_id, settings.doc_top_k * 3
    )
    if not candidates:
        return []

    vec = _minmax([h.score for h in candidates])
    corpus = [_tok(_text(h.payload)) for h in candidates]
    if any(corpus):
        bm = _minmax(list(BM25Okapi(corpus).get_scores(_tok(query))))
    else:
        bm = [0.0] * len(candidates)
    blended = [Hit(score=0.5 * v + 0.5 * b, payload=h.payload) for h, v, b in zip(candidates, vec, bm)]

    # rerank: 질의 토큰 커버리지(0.6) + 블렌드 점수(0.4)
    q = set(_tok(query))
    ranked = []
    for h in blended:
        cov = len(q & set(_tok(_text(h.payload)))) / len(q) if q else 0.0
        ranked.append(Hit(score=0.6 * cov + 0.4 * h.score, payload=h.payload))
    ranked.sort(key=lambda h: h.score, reverse=True)
    if category:
        ranked = [h for h in ranked if h.payload.get("category") == category] or ranked
    return ranked[: settings.doc_top_n]
