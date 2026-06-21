"""설정 — 환경변수 기반 (외부 의존성 최소화)."""
from __future__ import annotations

import os


class Settings:
    company_id: str = os.getenv("COMPANY_ID", "pizza")
    faq_collection: str = os.getenv("FAQ_COLLECTION", "faq_pizza")
    faq_threshold: float = float(os.getenv("FAQ_THRESHOLD", "0.85"))
    # 임베딩 백엔드: "hash" | "fastembed"(로컬 ONNX) | "remote"(중앙 임베딩 서버 API)
    embedding_backend: str = os.getenv("EMBEDDING_BACKEND", "hash")
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    embedding_dim: int = int(os.getenv("EMBEDDING_DIM", "384"))
    embedding_server_url: str = os.getenv("EMBEDDING_SERVER_URL", "http://127.0.0.1:9300")
    qdrant_host: str = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port: int = int(os.getenv("QDRANT_PORT", "6333"))
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "9001"))


settings = Settings()
