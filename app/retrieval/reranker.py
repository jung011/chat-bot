"""Rerank (§07 §4) — Hybrid 후보를 재정렬해 Top-N 만 생성에 투입한다.

운영에서는 cross-encoder Reranker(강의 스택)로 교체한다. 파일럿은 외부 모델
없이 동작하도록 경량 어휘 신호(질의 토큰 커버리지 + 기존 검색 점수)로 재점수한다.
인터페이스(rerank)는 동일하게 유지해 모델 교체 시 호출부 변경이 없도록 한다.
"""
from __future__ import annotations

import re

from app.retrieval.vector_store import Hit

_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


def _tok(text: str) -> set[str]:
    return set(_TOKEN_RE.findall(text.lower()))


def _text_of(payload: dict, text_field: str) -> str:
    if payload.get(text_field):
        return str(payload[text_field])
    parts = [str(payload.get(k, "")) for k in ("title", "question", "text", "answer")]
    return " ".join(p for p in parts if p)


def rerank(
    query: str,
    hits: list[Hit],
    *,
    top_n: int = 5,
    text_field: str = "text",
) -> list[Hit]:
    """질의 토큰 커버리지(0.6) + 기존 점수(0.4)로 재점수 후 Top-N."""
    q_tokens = _tok(query)
    if not q_tokens:
        return hits[:top_n]

    rescored: list[Hit] = []
    for h in hits:
        d_tokens = _tok(_text_of(h.payload, text_field))
        coverage = len(q_tokens & d_tokens) / len(q_tokens)
        score = 0.6 * coverage + 0.4 * h.score
        rescored.append(Hit(id=h.id, score=score, payload=h.payload))
    rescored.sort(key=lambda h: h.score, reverse=True)
    return rescored[:top_n]
