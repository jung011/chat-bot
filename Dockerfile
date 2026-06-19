# 멀티테넌트 RAG 챗봇 오케스트레이터 (FastAPI)
# 빌드: docker build -t chatbot-sample .
#   임베딩 fastembed 포함: docker build --build-arg EMBEDDING=fastembed -t chatbot-sample:fe .
# debian-slim 베이스 → manylinux 휠 사용(onnxruntime/grpcio/psycopg 컴파일 회피).

FROM python:3.12-slim

ENV PIP_NO_CACHE_DIR=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# ── 1) 의존성 레이어 (pyproject 변경 시에만 재실행 → 코드 수정엔 캐시 재사용) ──
#    deps 는 pyproject.toml 과 동기화(SSOT). 캐시 효율 위해 명시 설치.
RUN pip install --no-cache-dir \
    "fastapi>=0.110" "uvicorn[standard]>=0.27" "pydantic>=2.6" "pydantic-settings>=2.2" \
    "psycopg[binary,pool]>=3.1" "redis>=5.0" "qdrant-client>=1.7" "anthropic>=0.39" \
    "langgraph>=0.2" "mcp>=1.2" "pyyaml>=6.0" "rank-bm25>=0.2"

# ── 1b) (선택) 실제 임베딩 백엔드 — 무거운 onnxruntime 스택. 기본은 hash 라 미설치 ──
ARG EMBEDDING=base
RUN if [ "$EMBEDDING" = "fastembed" ]; then pip install --no-cache-dir "fastembed>=0.3"; fi

# ── 2) 소스 레이어 (코드만 바뀌면 여기부터 재빌드 — 빠름) ──
COPY app ./app
COPY configs ./configs
COPY run.py ./

EXPOSE 8000
CMD ["python", "run.py"]
