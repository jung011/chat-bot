"""설정 — 환경변수 기반 (외부 의존성 최소화)."""
from __future__ import annotations

import os


class Settings:
    company_id: str = os.getenv("COMPANY_ID", "pizza")
    documents_collection: str = os.getenv("DOCUMENTS_COLLECTION", "documents")
    # 업체 백엔드 API (정형/실시간 데이터 — 메뉴·매장·배달·주문). DB 는 백엔드가 소유.
    backend_url: str = os.getenv("BACKEND_URL", "http://127.0.0.1:9201")
    backend_timeout_seconds: float = float(os.getenv("BACKEND_TIMEOUT_SECONDS", "5.0"))
    # 임베딩 백엔드: "hash" | "fastembed"(로컬 ONNX) | "remote"(중앙 임베딩 서버 API)
    # ⚠️ documents 컬렉션은 오케스트레이터와 공유 → 동일 backend/model/dim 필수.
    embedding_backend: str = os.getenv("EMBEDDING_BACKEND", "hash")
    embedding_model: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    embedding_dim: int = int(os.getenv("EMBEDDING_DIM", "384"))
    embedding_server_url: str = os.getenv("EMBEDDING_SERVER_URL", "http://127.0.0.1:9300")
    doc_top_k: int = int(os.getenv("DOC_TOP_K", "20"))
    doc_top_n: int = int(os.getenv("DOC_TOP_N", "5"))
    qdrant_host: str = os.getenv("QDRANT_HOST", "localhost")
    qdrant_port: int = int(os.getenv("QDRANT_PORT", "6333"))
    host: str = os.getenv("HOST", "127.0.0.1")
    port: int = int(os.getenv("PORT", "9101"))


settings = Settings()
