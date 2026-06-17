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

> **LLM 백엔드 3가지 모드:**
> - `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` → Anthropic API
> - `LLM_PROVIDER=claude_cli` → **로컬 Claude Code CLI(`claude -p`) 사용, API 키 불필요** (설치된 `claude` 플랜으로 호출)
> - 키/CLI 없이 `anthropic` → FAQ 인터셉트·검색·자동완성은 동작하고, 생성/라우팅/agent 도구호출만 폴백/degrade
>
> 로컬 Claude 로 전체 흐름(생성·agent 도구호출)을 키 없이 돌리려면 `.env` 에 `LLM_PROVIDER=claude_cli` 설정.

## 설치 & 실행

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   /  macOS·Linux: source .venv/bin/activate
pip install -e ".[dev]"

# DB 스키마 초기화 + 데모 데이터 시드 (1회)
python scripts/init_db.py     # §04 테이블 생성
python scripts/seed_demo.py   # 피자/중국/치킨 메뉴·정책·FAQ·도구 적재

# (선택) 업체별 MCP 서버 6개 기동 — 별도 터미널 (A안)
python scripts/run_mcp_servers.py
#   FAQ:  pizza 9001 / chinese 9002 / chicken 9003
#   일반: pizza 9101 / chinese 9102 / chicken 9103
#   (FAQ만: python scripts/run_faq_servers.py)

# 메인 앱 실행 (권장 — 모든 OS에서 안전)
python run.py
```

> MCP 서버를 띄우지 않아도 동작한다(오케스트레이터가 인프로세스 호출로 자동 폴백).
> 띄우면 FAQ 인터셉트·도구 실행이 **업체별 독립 MCP 서버**(streamable-http)로 처리된다.

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
  mcp/           client(인프로세스) · faq_client · domain_client(업체별 서버 MCP 호출)
mcp_servers/     faq_template(업체별 FAQ) · general(업체별 일반) · domains(도메인 도구 단일소스)
indexing/        파싱→청킹→임베딩→적재 + 질문 생성
scripts/         init_db·seed_demo·schema.sql
```

계단형 필터: **자동완성(입력) → FAQ 시맨틱 인터셉트(0단계) → 라우팅 → Tool RAG/문서 RAG → 생성 → 검증**

## 파일럿 단순화 (운영 전환 시 교체)

- **임베딩**: 결정적 `HashEmbedder`(어휘 기반, 키 불필요). 운영은 실제 임베딩 모델로 교체
  (`app/retrieval/embedder.py` 의 `Embedder` 인터페이스). 조사/어형이 다른 의역 매칭은 실제 모델 필요.
- **FAQ 서버(A안, 실제 분리)**: 업체별 FAQ MCP 서버가 **독립 프로세스/포트**로 뜬다
  (`mcp_servers/faq_template` 코드 1벌 + `config/faq_<id>.yaml` 설정만 다르게, §01 §6).
  오케스트레이터는 `app/mcp/faq_client.py` 로 **표준 MCP 프로토콜(streamable-http)** 호출
  → 미기동 시 인프로세스 폴백. (벡터DB 는 아직 공용 Qdrant + 컬렉션 `faq_<id>`; 인스턴스 분리는 운영 전환.)
- **일반(도메인) MCP 서버(A안, 실제 분리)**: 업체별 일반 MCP 서버가 **독립 프로세스/포트**(9101~3)로 뜬다
  (`mcp_servers/general` — 도메인 도구 `documents·store·order` 7개를 묶음, 코드 1벌 + `config/general_<id>.yaml`).
  오케스트레이터는 `app/mcp/domain_client.py` 로 **표준 MCP 프로토콜** 호출 → 미기동 시 인프로세스 폴백.
- **Tool RAG company_id 필터**: `tools` 컬렉션을 업체별로 태깅 적재(`index_tools(catalog, company_id)`).
  `tool_retriever.retrieve_tools(query, company_id=...)` 가 그 업체 도구로만 후보를 검색 → LLM 에 다른 업체 도구를 노출하지 않음.
- **관리자 인증**: 단일 공유 토큰(`ADMIN_TOKEN`). 운영은 `admins` 테이블 기반 per-company.
- **인덱싱 잡**: `/v1/admin/index` 는 작업 기록만(워커 미구현).
