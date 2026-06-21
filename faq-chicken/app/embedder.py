"""임베딩 — 결정적 HashEmbedder (의존성 없음).

⚠️ 인덱싱(시드) 시 사용한 임베더와 **동일한 토큰화·해싱**이어야 기존
faq_<id> 컬렉션의 벡터와 매칭된다. (운영에선 벤더 자체 임베딩 모델로 교체)
"""
from __future__ import annotations

import hashlib
import math
import re

_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


class HashEmbedder:
    def __init__(self, dim: int):
        self.dim = dim

    def embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for tok in _TOKEN_RE.findall(text.lower()):
            h = hashlib.sha1(tok.encode("utf-8")).digest()
            i1 = int.from_bytes(h[0:4], "little") % self.dim
            i2 = int.from_bytes(h[4:8], "little") % self.dim
            vec[i1] += 1.0
            vec[i2] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            vec[0] = 1.0
            return vec
        return [v / norm for v in vec]
