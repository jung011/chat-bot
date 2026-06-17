"""애플리케이션 설정 (환경변수 → Pydantic Settings).

DB 접속정보 등은 코드에 하드코딩하지 않고 .env 에서 읽는다.
(문서 02 §6, 04 전제: 기존 로컬 도커 컨테이너에 연결)
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 프로젝트 루트 (이 파일: app/core/config.py → 2단계 상위)
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "chatbot-backend"
    env: str = "local"
    api_prefix: str = "/v1"

    # 테넌트 레지스트리 (단일 소스, §02 §6)
    tenants_file: str = str(BASE_DIR / "configs" / "tenants.yaml")

    # 관리자 API 인증 토큰 (§03 §1.2). 비어 있으면 관리자 API 비활성(401).
    admin_token: str = ""

    # 검색/임베딩 (§07 §4.1) — 기본값, tenants.yaml defaults 로 덮어씀
    embedding_dim: int = 384
    faq_threshold: float = 0.85
    doc_top_k: int = 20
    doc_top_n: int = 5
    tool_top_k: int = 5

    # 오케스트레이션 루프 상한 (§06 §9)
    max_tool_iters: int = 3

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_db: str = "app"

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333

    # LLM (Claude)
    anthropic_api_key: str = ""
    llm_model_light: str = "claude-haiku-4-5-20251001"
    llm_model_main: str = "claude-sonnet-4-6"
    llm_model_heavy: str = "claude-opus-4-8"
    llm_timeout_seconds: int = 60

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
