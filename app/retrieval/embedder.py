"""임베딩 (§07 §3.3).

인덱싱/질의에 **동일 모델**을 사용해야 한다(§07 §3.3). 본 파일럿은 외부 API/키
없이도 색인·검색이 일관되게 동작하도록 결정적(deterministic) `HashEmbedder`를
기본 제공한다. 운영에서는 동일 인터페이스(`Embedder`)를 구현하는 실제 임베딩
모델(예: Voyage/OpenAI/sentence-transformers, 한국어 성능 우선 §07 §7)로 교체한다.

⚠️ HashEmbedder 는 의미(semantic) 임베딩이 아니라 토큰 해시 기반의 의사
임베딩이다. 동일/유사 토큰을 공유하는 문장은 가깝게 매핑되어 데모 검색은
동작하지만, 진짜 의미 유사도는 실제 모델로 교체해야 확보된다.
"""
from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from app.core.config import settings

_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


class Embedder(Protocol):
    dim: int

    def embed(self, text: str) -> list[float]: ...

    def embed_many(self, texts: list[str]) -> list[list[float]]: ...


class HashEmbedder:
    """토큰 해시 → bag-of-tokens 벡터 → L2 정규화. 결정적, 의존성 없음."""

    def __init__(self, dim: int | None = None):
        self.dim = dim or settings.embedding_dim

    def _tokens(self, text: str) -> list[str]:
        return _TOKEN_RE.findall(text.lower())

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in self._tokens(text):
            # 토큰을 두 개의 해시 버킷에 분산(충돌 완화)
            h = hashlib.sha1(tok.encode("utf-8")).digest()
            i1 = int.from_bytes(h[0:4], "little") % self.dim
            i2 = int.from_bytes(h[4:8], "little") % self.dim
            vec[i1] += 1.0
            vec[i2] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            # 빈/토큰없음 입력은 0 벡터 대신 안정적 단위벡터로(검색 안전)
            vec[0] = 1.0
            return vec
        return [v / norm for v in vec]

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


class FastEmbedEmbedder:
    """로컬 ONNX 실제 임베딩 모델(fastembed). 의미 유사도 기반 — 조사/어형 변화에 강함.

    API 키 불필요. 최초 1회 모델 다운로드 후 로컬 추론. COSINE 거리는 Qdrant 가
    정규화하므로 별도 L2 정규화 없이 모델 출력을 그대로 사용한다.
    """

    def __init__(self, model_name: str | None = None, dim: int | None = None):
        from fastembed import TextEmbedding

        self.dim = dim or settings.embedding_dim
        self._model = TextEmbedding(model_name=model_name or settings.embedding_model)

    def embed(self, text: str) -> list[float]:
        return list(self._model.embed([text]))[0].tolist()

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.embed(list(texts))]


_embedder: Embedder | None = None


def get_embedder() -> Embedder:
    """전역 임베더. settings.embedding_backend 로 구현 선택(hash | fastembed)."""
    global _embedder
    if _embedder is None:
        if settings.embedding_backend == "fastembed":
            _embedder = FastEmbedEmbedder()
        else:
            _embedder = HashEmbedder()
    return _embedder
