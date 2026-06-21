"""설정 — 환경변수 기반 (외부 의존성 최소화)."""
from __future__ import annotations

import os


class Settings:
    company_id: str = os.getenv("COMPANY_ID", "chicken")
    documents_collection: str = os.getenv("DOCUMENTS_COLLECTION", "documents")
    embedding_dim: int = int(os.getenv("EMBEDDING_DIM", "384"))
    doc_top_k: int = int(os.getenv("DOC_TOP_K", "20"))
    doc_top_n: int = int(os.getenv("DOC_TOP_N", "5"))
    qdrant_host: str = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port: int = int(os.getenv("QDRANT_PORT", "6333"))
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "9103"))


settings = Settings()
