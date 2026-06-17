"""Hybrid 검색 (벡터 + BM25) — §07 §4.

메뉴명·"양념"·"반반" 등 키워드 매칭은 BM25 가 강하므로 벡터와 결합한다(§07 §4.1).
구현: 벡터로 후보를 과다추출(over-fetch) → 후보 텍스트에 BM25 재점수 →
정규화 점수를 alpha 로 블렌딩. (별도 BM25 인덱스 없이 후보군에만 적용 — 파일럿)
"""
from __future__ import annotations

import re

from rank_bm25 import BM25Okapi

from app.retrieval import vector_store
from app.retrieval.vector_store import Hit

_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


def _tok(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


def _minmax(scores: list[float]) -> list[float]:
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi - lo < 1e-9:
        return [1.0 for _ in scores]
    return [(s - lo) / (hi - lo) for s in scores]


def _payload_text(payload: dict, text_field: str) -> str:
    # 우선 지정 필드, 없으면 흔한 후보들을 합친다.
    if payload.get(text_field):
        return str(payload[text_field])
    parts = [str(payload.get(k, "")) for k in ("title", "question", "text", "answer")]
    return " ".join(p for p in parts if p)


async def search(
    collection: str,
    query: str,
    *,
    company_id: str | None = None,
    top_k: int = 20,
    alpha: float = 0.5,
    text_field: str = "text",
    over_fetch: int = 3,
) -> list[Hit]:
    """alpha: 벡터 가중치(1.0=벡터만, 0.0=BM25만). 블렌딩 점수로 정렬해 top_k 반환."""
    candidates = await vector_store.search(
        collection, query, company_id=company_id, top_k=top_k * over_fetch
    )
    if not candidates:
        return []

    vec_scores = _minmax([h.score for h in candidates])

    corpus = [_tok(_payload_text(h.payload, text_field)) for h in candidates]
    if any(corpus):
        bm25 = BM25Okapi(corpus)
        raw = list(bm25.get_scores(_tok(query)))
        bm25_scores = _minmax(raw)
    else:
        bm25_scores = [0.0] * len(candidates)

    blended: list[Hit] = []
    for h, v, b in zip(candidates, vec_scores, bm25_scores):
        score = alpha * v + (1 - alpha) * b
        blended.append(Hit(id=h.id, score=score, payload=h.payload))
    blended.sort(key=lambda h: h.score, reverse=True)
    return blended[:top_k]
