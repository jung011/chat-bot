# chatbot-backend

멀티테넌트 RAG 챗봇 백엔드 (FastAPI). 설계 문서는 [`docs/`](./docs) 참고.

- 테넌트: 피자집(`pizza`) / 중국집(`chinese`) / 치킨집(`chicken`)
- DB는 **기존 로컬 도커 컨테이너**(`git/Docker/docker-compose.yml`)에 연결 — Postgres / Redis / Qdrant

## 사전 준비

1) DB 컨테이너 기동 (별도 Docker 폴더에서)
```bash
cd ../Docker && docker compose up -d
```

2) 환경 변수
```bash
cp .env.example .env   # 필요 시 값 수정 (ANTHROPIC_API_KEY 등)
```

> **ANTHROPIC_API_KEY 없이도** 동작한다. FAQ 인터셉트·검색·자동완성은 키 없이 작동하고,
> 최종 답변 생성(LLM)만 폴백 문구로 degrade 된다. 키를 넣으면 생성·라우팅·재작성이 활성화된다.

## 설치 & 실행

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   /  macOS·Linux: source .venv/bin/activate
pip install -e ".[dev]"

# DB 스키마 초기화 + 데모 데이터 시드 (1회)
python scripts/init_db.py     # §04 테이블 생성
python scripts/seed_demo.py   # 피자/중국/치킨 메뉴·정책·FAQ·도구 적재

# 실행 (권장 — 모든 OS에서 안전)
python run.py
```

> **Windows 주의:** 반드시 `python run.py` 로 실행한다.
> Windows 기본 asyncio 루프(ProactorEventLoop)는 psycopg(async)를 지원하지
> 않아 `uvicorn app.main:app` 으로 직접 띄우면 Postgres 연결이 실패한다.
> `run.py` 는 루프 생성 전에 `WindowsSelectorEventLoopPolicy` 를 설정한다.
> (macOS·Linux는 `uvicorn app.main:app --reload --port 8000` 도 무방)

## 확인

```bash
curl http://localhost:8000/v1/health
# {"data":{"status":"degraded","dependencies":{"postgres":"ok","redis":"ok","vector_db":"ok","llm":"not_configured"}}}

# FAQ 즉답(LLM 불필요) — route=faq_intercept
curl -X POST http://localhost:8000/v1/chat/sync -H "Content-Type: application/json" \
  -d '{"company_id":"pizza","message":"영업시간이 어떻게 되나요?"}'
```

- API 문서(Swagger): http://localhost:8000/docs
- 테스트: `pytest` (통합 테스트는 DB 기동 + 시드 필요)

## 엔드포인트 (§03)

| 메서드 | 경로 | 설명 |
|---|---|---|
| POST | `/v1/chat` | 채팅(SSE 스트리밍) |
| POST | `/v1/chat/sync` | 채팅(비스트리밍) |
| GET | `/v1/autocomplete` | 입력 자동완성 |
| POST/GET/DELETE | `/v1/sessions[...]` | 세션 관리 |
| POST | `/v1/messages/{id}/feedback` | 피드백 |
| POST | `/v1/admin/faq` · `/v1/admin/index` | 관리자(토큰 필요) |
| GET | `/v1/health` | 헬스체크 |

## 구조 (§01·§02 대응)

```
app/
  api/v1/        엔드포인트(얇게) + deps(테넌트/관리자 인증)
  services/      chat·autocomplete·admin 유스케이스
  orchestration/ LangGraph 그래프 + 노드(rewrite·route·tool_select·generate·verify)
  retrieval/     embedder·vector_store·hybrid·reranker·tool_retriever
  tenancy/       레지스트리(configs/tenants.yaml) + 결정적 라우터
  llm/           Claude 클라이언트 + 모델 티어(Haiku/Sonnet/Opus)
  memory/        Redis 단기 대화
  autocomplete/  prefix+시맨틱 추천
  mcp/client.py  도구 호출(인프로세스 레지스트리)
mcp_servers/     FAQ 템플릿 + 도메인 도구(documents·store·order, FastMCP)
indexing/        파싱→청킹→임베딩→적재 + 질문 생성
scripts/         init_db·seed_demo·schema.sql
```

계단형 필터: **자동완성(입력) → FAQ 시맨틱 인터셉트(0단계) → 라우팅 → Tool RAG/문서 RAG → 생성 → 검증**

## 파일럿 단순화 (운영 전환 시 교체)

- **임베딩**: 결정적 `HashEmbedder`(어휘 기반, 키 불필요). 운영은 실제 임베딩 모델로 교체
  (`app/retrieval/embedder.py` 의 `Embedder` 인터페이스). 조사/어형이 다른 의역 매칭은 실제 모델 필요.
- **MCP**: 도구는 단일 소스(`mcp_servers/.../tools.py`). FastMCP `server.py` 로 독립 배포 가능하나,
  오케스트레이터는 `app/mcp/client.py` 인프로세스 레지스트리로 호출(테스트 용이). 운영은 표준 MCP 프로토콜로 교체.
- **FAQ 격리(A안)**: 파일럿은 공용 Qdrant + 업체별 컬렉션(`faq_<id>`). 운영은 업체별 인스턴스 분리.
- **관리자 인증**: 단일 공유 토큰(`ADMIN_TOKEN`). 운영은 `admins` 테이블 기반 per-company.
- **인덱싱 잡**: `/v1/admin/index` 는 작업 기록만(워커 미구현).
