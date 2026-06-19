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
    # (FAQ 임계값은 faq 서버가 소유 — 오케스트레이터에 두지 않음)
    # embedding_backend: "hash"(결정적 의사임베딩, 기본) | "fastembed"(로컬 ONNX 실제 모델)
    #   ⚠️ documents 컬렉션은 general-* 벤더 서버와 공유하므로 동일 backend/model/dim 이어야 함.
    # embedding_backend: "hash" | "fastembed"(인프로세스 ONNX) | "remote"(중앙 임베딩 서버 API)
    embedding_backend: str = "hash"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_dim: int = 384
    # backend=remote 일 때 호출할 중앙 임베딩 서버 URL(모델 일관성 구조적 보장)
    embedding_server_url: str = "http://127.0.0.1:9300"
    doc_top_k: int = 20
    doc_top_n: int = 5
    tool_top_k: int = 5

    # FAQ 검색 소스(정공법) 튜닝
    faq_search_top_k: int = 5      # search_faq 후보 수(rag/agent 컨텍스트 병합용)
    # 무관 FAQ 제외 floor — ⚠️ embedding_backend 와 짝(분포가 모델마다 다름).
    # fastembed: 관련 0.48~0.92 / 무관 ~0.16 → 0.3. hash 는 무관이 ~0 이라 더 낮아도 무방.
    faq_score_floor: float = 0.3

    # MCP 외부 서버 호출 타임아웃(초) — 운영망 지연에 맞게 조정
    mcp_call_timeout_seconds: float = 10.0   # 일반(도메인) 서버 도구 호출
    faq_call_timeout_seconds: float = 5.0    # FAQ 서버 match/search

    # 오케스트레이션 루프 상한 (§06 §9)
    max_tool_iters: int = 3

    # 라우팅 방식 — "rule"(규칙, LLM 호출 0, 기본) | "llm"(Haiku 분류) | "hybrid"(규칙→모호시 LLM)
    # rule 기본: 일반 RAG 질의의 LLM 호출을 2회(route+generate)→1회(generate)로 줄여 지연 단축.
    route_mode: str = "rule"

    # 검증(verify) 노드 — 선택(§06 §4.5). 경량 모델 판사가 근거 있는 답을 오기각하는
    # 경우가 있어 기본 OFF. 생성 프롬프트가 이미 '컨텍스트 외 답변 금지'를 강제한다.
    verify_enabled: bool = False

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
    # llm_provider: "anthropic"(API 키) | "claude_cli"(로컬 Claude Code CLI, 키 불필요)
    llm_provider: str = "anthropic"
    claude_cli_path: str = "claude"
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
