"""임베딩 — HashEmbedder(기본) | FastEmbedEmbedder(로컬 ONNX 실제 모델).

⚠️ documents 컬렉션은 오케스트레이터와 공유 → 인덱싱/질의가 동일 backend/model/dim
이어야 매칭된다. backend 는 settings.embedding_backend 로 선택.
"""
from __future__ import annotations

import hashlib
import math
import re

from app.config import settings

_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


class HashEmbedder:
    def __init__(self, dim: int):
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in _TOKEN_RE.findall(text.lower()):
            h = hashlib.sha1(tok.encode("utf-8")).digest()
            vec[int.from_bytes(h[0:4], "little") % self.dim] += 1.0
            vec[int.from_bytes(h[4:8], "little") % self.dim] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            vec[0] = 1.0
            return vec
        return [v / norm for v in vec]


class FastEmbedEmbedder:
    """로컬 ONNX 실제 임베딩 모델(fastembed) — 의미 유사도. API 키 불필요."""

    def __init__(self, model_name: str, dim: int):
        from fastembed import TextEmbedding

        self.dim = dim
        self._model = TextEmbedding(model_name=model_name)

    def embed(self, text: str) -> list[float]:
        return list(self._model.embed([text]))[0].tolist()


class RemoteEmbedder:
    """중앙 임베딩 서버(HTTP) 호출 — 모델 일관성 구조적 보장, 클라이언트 경량."""

    def __init__(self, url: str, dim: int):
        import httpx

        self.url = url.rstrip("/")
        self.dim = dim
        self._client = httpx.Client(timeout=10.0)

    def embed(self, text: str) -> list[float]:
        r = self._client.post(f"{self.url}/embed", json={"texts": [text]})
        r.raise_for_status()
        return r.json()["vectors"][0]


_embedder = None


def get_embedder():
    """전역 임베더 — settings.embedding_backend 로 구현 선택(hash | fastembed | remote)."""
    global _embedder
    if _embedder is None:
        if settings.embedding_backend == "fastembed":
            _embedder = FastEmbedEmbedder(settings.embedding_model, settings.embedding_dim)
        elif settings.embedding_backend == "remote":
            _embedder = RemoteEmbedder(settings.embedding_server_url, settings.embedding_dim)
        else:
            _embedder = HashEmbedder(settings.embedding_dim)
    return _embedder
