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

# (선택) 외부 MCP 서버 6개 기동 — 독립 프로젝트(상위 git/ 폴더의 형제), 별도 터미널 (A안)
python scripts/run_external_servers.py
#   FAQ:  faq-pizza 9001 / faq-chinese 9002 / faq-chicken 9003
#   일반: general-pizza 9101 / general-chinese 9102 / general-chicken 9103
#   (각 프로젝트는 자체 venv 필요 — 각 폴더에서 python -m venv .venv && pip install -e .)

# 외부 서버 기동 후, 도구를 디스커버리해 Tool RAG 색인 (general 서버 list_tools)
python scripts/index_tools.py

# 메인 앱 실행 (권장 — 모든 OS에서 안전)
python run.py
```

> **MCP 서버는 별도 독립 프로젝트**로 분리됨(상위 `git/` 폴더의 `faq-*`, `general-*`).
> 각각 자체 의존성/venv 를 가진 FastAPI+FastMCP 서비스(외부 벤더가 개발한 것처럼). 오케스트레이터는
> 표준 MCP 프로토콜로 호출(원격 전용). 매칭/도구 로직은 서버가 소유하므로 오케스트레이터엔 중복 없음.

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
  mcp/           faq_client · domain_client (외부 서버 MCP 호출, 원격 전용)
                 # 도구 목록은 외부 서버 list_tools 로 디스커버리(scripts/index_tools.py) — 하드코딩 카탈로그 없음

# MCP 서버는 외부 독립 프로젝트(상위 git/ 폴더):
#   faq-{pizza,chinese,chicken}      FastAPI+FastMCP, match_faq (포트 9001~3)
#   general-{pizza,chinese,chicken}  FastAPI+FastMCP, 도메인 도구 7개 (포트 9101~3)
indexing/        파싱→청킹→임베딩→적재 + 질문 생성
scripts/         init_db·seed_demo·schema.sql
```

계단형 필터: **자동완성(입력) → FAQ 시맨틱 인터셉트(0단계) → 라우팅 → Tool RAG/문서 RAG → 생성 → 검증**

## 파일럿 단순화 (운영 전환 시 교체)

- **임베딩**: 결정적 `HashEmbedder`(어휘 기반, 키 불필요). 운영은 실제 임베딩 모델로 교체
  (`app/retrieval/embedder.py` 의 `Embedder` 인터페이스). 조사/어형이 다른 의역 매칭은 실제 모델 필요.
- **MCP 서버 = 외부 독립 프로젝트(A안)**: FAQ·일반 서버가 상위 `git/` 폴더의 **별도 프로젝트**
  (`faq-{pizza,chinese,chicken}`, `general-{pizza,chinese,chicken}`)로 분리됨. 각각 **자체
  pyproject + venv + 코드**(embedder/검색 로직 자체 보유, 다른 프로젝트 import 0) — 외부 벤더가
  독립 개발한 것처럼. 모두 **FastAPI + FastMCP**(streamable-http, `/mcp` + `/health`).
  - 오케스트레이터는 `app/mcp/faq_client.py`·`domain_client.py` 로 **표준 MCP 프로토콜**(원격 전용) 호출.
    매칭/도구 로직·임계값은 **서버가 소유** — 오케스트레이터에 중복 없음(서버 미가동 시 FAQ 는 통과→rag, 도구는 답변 실패).
  - 데이터(Qdrant)는 공유(컬렉션/필터 격리). 코드/의존성만 분리.
- **Tool RAG = 서버 디스커버리**: `scripts/index_tools.py` 가 각 general 서버의 MCP `list_tools` 로 도구를
  발견해 `tools` 컬렉션에 업체별 태깅 적재(하드코딩 카탈로그 없음 — 도구 정의의 단일 출처 = 서버).
  `tool_retriever.retrieve_tools(query, company_id=...)` 가 그 업체 도구로만 후보 검색.
- **관리자 인증**: 단일 공유 토큰(`ADMIN_TOKEN`). 운영은 `admins` 테이블 기반 per-company.
- **인덱싱 잡**: `/v1/admin/index` 는 작업 기록만(워커 미구현).
