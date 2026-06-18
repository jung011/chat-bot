# API 명세서 (FastAPI)

> **대상:** 백엔드/프론트 개발팀
> **목적:** 챗봇 백엔드가 제공하는 HTTP API의 엔드포인트·요청/응답 계약을 정의한다.
> **관련 문서:** [01_아키텍처_설계서.md](./01_아키텍처_설계서.md) · [02_백엔드_패키지구조.md](./02_백엔드_패키지구조.md) · [04_DB설계서.md](./04_DB설계서.md)
> **상태:** 초안 (v1)

> ⚠️ **구현 현황(as-built):** 엔드포인트 계약은 구현과 일치. 동작 차이: `POST /v1/admin/faq` 는 임베딩/적재를 직접 하지 않고 **faq 벤더 서버 `upsert_faq` 에 위임**(이력은 메타DB 기록). `POST /v1/admin/index` 는 잡만 기록(워커 미구현). 라우팅 기본 규칙 기반(meta.route). 자세한 구현은 [12_구현_아키텍처.md](./12_구현_아키텍처.md).

---

## 1. 공통 규약

### 1.1 기본 정보

| 항목 | 값 |
|---|---|
| Base URL | `/v1` |
| 프로토콜 | HTTPS |
| 요청/응답 포맷 | `application/json` (스트리밍은 `text/event-stream`) |
| 인코딩 | UTF-8 |

### 1.2 테넌트 식별 (비회원 구조)

본 서비스 **고객용 API는 비회원(로그인 없음)** 구조다. 인증 토큰 대신 **`company_id`를 요청에서 직접 받는다.**

- **고객용 API**(chat / autocomplete / sessions): **인증 불필요.** `company_id`를 요청 파라미터로 전달.
  - chat 계열: 요청 body의 `company_id`
  - GET 계열: 쿼리 파라미터 `company_id`
- **관리자 API**(admin/*): **인증 필수**(관리자 키/토큰). 비회원 공개 금지.
- 서버는 받은 `company_id`로 테넌트 라우팅 및 모든 데이터 필터를 적용한다.

```
# 고객용: 토큰 없음, company_id 직접 전달
Content-Type: application/json
X-Request-Id: <선택, 클라이언트 추적용>

# 관리자용: 인증 필요
Authorization: Bearer <admin_token>
```

> ⚠️ **보안 트레이드오프(의도된 설계).** `company_id`가 클라이언트 입력이므로 고객용 데이터에는 **접근 통제가 없다**(임의 company_id로 타 업체 공개정보 조회 가능). 고객용 데이터는 **공개 정보(메뉴·영업·배달)**라 허용한다. 단,
> - 관리자 API는 반드시 인증 유지(데이터 변조 방지).
> - 저장소 격리(FAQ 인스턴스 분리 등 §01 §6)는 그대로 유지 — "접근 통제"만 공개.
> - 비회원이라 사용자 식별이 없으므로 레이트리밋은 **IP/세션 기준**(§4)으로 강화.
> - 유효하지 않은 `company_id`는 `400 INVALID_REQUEST`.

### 1.3 공통 응답 형식

성공:
```json
{ "data": { ... }, "request_id": "req_abc123" }
```

에러:
```json
{
  "error": {
    "code": "INVALID_REQUEST",
    "message": "사람이 읽을 수 있는 설명",
    "details": { }
  },
  "request_id": "req_abc123"
}
```

### 1.4 표준 상태 코드

| 코드 | 의미 |
|---|---|
| 200 | 성공 |
| 201 | 생성됨 |
| 400 | 잘못된 요청(검증 실패) |
| 401 | 인증 실패(관리자 API 토큰 없음/만료) |
| 403 | 권한 없음(타 테넌트 접근 등) |
| 404 | 리소스 없음 |
| 422 | 의미적 검증 실패(Pydantic) |
| 429 | 레이트리밋 초과 |
| 500 | 서버 오류 |
| 503 | 의존 서비스(벡터DB/LLM) 불가 |
| 504 | 응답 시간 초과(LLM 타임아웃) |

### 1.5 에러 코드 목록

| code | 설명 |
|---|---|
| `INVALID_REQUEST` | 필수 파라미터 누락/형식 오류 |
| `UNAUTHORIZED` | 인증 실패(관리자 API 전용) |
| `TENANT_FORBIDDEN` | 다른 테넌트 리소스 접근 시도 |
| `SESSION_NOT_FOUND` | 세션 없음 |
| `RATE_LIMITED` | 요청 한도 초과 |
| `UPSTREAM_UNAVAILABLE` | LLM/벡터DB 등 의존 서비스 오류 |
| `LLM_TIMEOUT` | LLM 응답이 제한 시간(60초)을 초과 |

### 1.5.1 타임아웃 정책

| 항목 | 값 |
|---|---|
| LLM 응답 타임아웃 | **60초** (설정값으로 외부화) |
| 적용 범위 | 단일 LLM 호출 기준. 다단계 루프는 단계별 적용 |
| 초과 시(sync) | `504` + `LLM_TIMEOUT` + 폴백 메시지 |
| 초과 시(streaming) | `error` 이벤트(`LLM_TIMEOUT`) 전송 후 폴백 메시지로 종료 |

**폴백 메시지(사용자 노출):**
> "답변을 준비하는 데 시간이 조금 오래 걸리고 있어요. 😅 잠시 후 다시 시도해 주시거나, 질문을 조금만 더 구체적으로 입력해 주시면 더 빠르게 도와드릴게요."

> 짧은 버전(위젯/모바일): "지금 답변이 지연되고 있어요. 잠시 후 다시 시도해 주세요. 🙏"

### 1.6 페이지네이션

목록 조회는 커서 기반:
```
GET /v1/sessions?limit=20&cursor=<opaque>
→ { "data": [...], "next_cursor": "..." | null }
```

---

## 2. 엔드포인트 요약

| 메서드 | 경로 | 설명 | 인증 | company_id |
|---|---|---|---|---|
| POST | `/v1/chat` | 메시지 전송 → 답변(스트리밍) | ❌ | body |
| POST | `/v1/chat/sync` | 메시지 전송 → 답변(비스트리밍) | ❌ | body |
| GET | `/v1/autocomplete` | 입력 자동완성 후보 | ❌ | query |
| GET | `/v1/sessions` | 세션 목록 | ❌ | query |
| POST | `/v1/sessions` | 새 세션 생성 | ❌ | body |
| GET | `/v1/sessions/{session_id}/messages` | 세션 대화 내역 | ❌ | query |
| DELETE | `/v1/sessions/{session_id}` | 세션 삭제 | ❌ | query |
| POST | `/v1/messages/{message_id}/feedback` | 답변 피드백 | ❌ | body |
| POST | `/v1/admin/faq` | FAQ 업로드(담당자) | ✅(admin) | 토큰 |
| POST | `/v1/admin/index` | 인덱싱 작업 트리거 | ✅(admin) | 토큰 |
| GET | `/v1/health` | 헬스체크 | ❌ | — |

> 고객용은 비회원(인증 ❌) + `company_id` 직접 수신. 관리자용만 인증 + 토큰의 company_id 사용(§1.2).

---

## 3. 엔드포인트 상세

### 3.1 POST `/v1/chat` — 채팅 (스트리밍)

사용자 질문을 받아 오케스트레이션 파이프라인(FAQ 인터셉트 → Tool RAG → 생성)을 거쳐 **SSE로 토큰 스트리밍** 응답한다.

**Request Body**
```json
{
  "company_id": "pizza",           // 필수 (비회원 — 클라이언트가 직접 전달)
  "session_id": "sess_123",        // 없으면 서버가 새로 생성
  "message": "영업시간이 어떻게 되나요?",
  "stream": true                   // 기본 true
}
```

| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `company_id` | string | ✅ | 업체 식별자 (pizza/chinese/chicken). 유효하지 않으면 `400` |
| `session_id` | string | ❌ | 없으면 신규 세션 생성 후 반환 |
| `message` | string | ✅ | 사용자 질문 (1~4000자) |
| `stream` | bool | ❌ | 기본 true |

**Response — `text/event-stream` (SSE)**

이벤트 타입별 스트림:
```
event: meta
data: {"session_id":"sess_123","message_id":"msg_789","route":"faq_intercept"}

event: token
data: {"text":"영업시간은 "}

event: token
data: {"text":"평일 9시부터 18시까지입니다."}

event: sources
data: {"sources":[{"type":"faq","title":"영업시간 안내","score":0.92}]}

event: done
data: {"finish_reason":"stop","usage":{"input_tokens":120,"output_tokens":35}}
```

| event | 데이터 | 설명 |
|---|---|---|
| `meta` | session_id, message_id, **route** | 어떤 경로로 처리됐는지(`faq_intercept`/`rag`/`agent`) |
| `token` | text | 생성 토큰 조각 |
| `sources` | sources[] | 근거(FAQ/문서/도구) |
| `done` | finish_reason, usage | 종료 + 토큰 사용량 |
| `error` | code, message | 스트림 중 오류 |

> **route 필드**는 디버깅·분석에 중요(계단형 필터 어디서 처리됐는지). FAQ 즉답이면 `faq_intercept`라 LLM 토큰 사용량이 0에 가깝다.

**상태 코드:** 200(스트림 시작), 400(잘못된/누락 company_id)/429/503/504

---

### 3.2 POST `/v1/chat/sync` — 채팅 (비스트리밍)

스트리밍이 불가한 클라이언트/배치용. 전체 답변을 한 번에 반환.

**Request:** `/v1/chat`과 동일 (`stream:false` 권장)

**Response 200**
```json
{
  "data": {
    "session_id": "sess_123",
    "message_id": "msg_789",
    "route": "rag",
    "answer": "영업시간은 평일 9시부터 18시까지입니다.",
    "sources": [
      {"type": "faq", "title": "영업시간 안내", "score": 0.92}
    ],
    "usage": {"input_tokens": 120, "output_tokens": 35}
  },
  "request_id": "req_abc123"
}
```

---

### 3.3 GET `/v1/autocomplete` — 자동완성

입력 중인 텍스트에 대해 **답 가능한 질문 후보**를 반환(§01 §4.8). 매 키스트로크 호출되므로 초고속.

**Query Params**

| 파라미터 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `company_id` | string | ✅ | 업체 식별자 |
| `q` | string | ✅ | 입력 중 텍스트(prefix) |
| `limit` | int | ❌ | 기본 8, 최대 20 |

```
GET /v1/autocomplete?company_id=pizza&q=영업&limit=8
```

**Response 200**
```json
{
  "data": {
    "query": "영업",
    "suggestions": [
      {"text": "영업시간이 어떻게 되나요?", "source": "faq"},
      {"text": "영업일은 언제인가요?", "source": "document"},
      {"text": "영업점 위치가 어디인가요?", "source": "log"}
    ]
  },
  "request_id": "req_abc124"
}
```

| 필드 | 설명 |
|---|---|
| `source` | 후보 출처: `faq` / `document`(문서기반 생성) / `log`(질문 로그) |

> 후보는 **company_id로 필터**된 풀에서만 추출(테넌트 격리). prefix 매칭(Trie/DB) 우선, 입력 멈춤 시 시맨틱 보강 가능.

---

### 3.4 세션 관리

#### POST `/v1/sessions` — 세션 생성
**Request**
```json
{ "company_id": "pizza", "title": "신규 문의" }   // company_id 필수, title 선택
```
**Response 201**
```json
{ "data": { "session_id": "sess_123", "created_at": "2026-06-17T09:00:00Z" } }
```

#### GET `/v1/sessions` — 세션 목록
```
GET /v1/sessions?company_id=pizza&limit=20&cursor=...
```
```json
{
  "data": [
    {"session_id":"sess_123","title":"신규 문의","updated_at":"2026-06-17T09:10:00Z"}
  ],
  "next_cursor": null
}
```

#### GET `/v1/sessions/{session_id}/messages` — 대화 내역
```json
{
  "data": [
    {"message_id":"msg_1","role":"user","content":"영업시간?","created_at":"..."},
    {"message_id":"msg_2","role":"assistant","content":"평일 9~18시","route":"faq_intercept","created_at":"..."}
  ],
  "next_cursor": null
}
```

#### DELETE `/v1/sessions/{session_id}` — 세션 삭제
```
DELETE /v1/sessions/{session_id}?company_id=pizza
```
**Response 200** `{ "data": { "deleted": true } }`

> 비회원 구조라 세션은 **클라이언트 보관 `session_id` + 전달된 `company_id`로 조회/필터**한다. 세션의 `company_id`와 요청 `company_id`가 다르면 `404`(노출 최소화). 사용자 계정 기반 소유권 검증은 없음.

---

### 3.5 POST `/v1/messages/{message_id}/feedback` — 피드백

답변 품질 피드백 수집(향후 FAQ 자동 적재/개선에 활용).

**Request**
```json
{ "company_id": "pizza", "rating": "up", "reason": "정확함" }   // rating: "up" | "down"
```
**Response 200** `{ "data": { "recorded": true } }`

---

### 3.6 관리자 API (담당자/운영)

#### POST `/v1/admin/faq` — FAQ 업로드
업체 담당자가 제출한 FAQ를 해당 테넌트 풀에 적재(임베딩 파이프라인 트리거).

**Request** (`multipart/form-data` 또는 JSON 배열)
```json
{
  "items": [
    {"question": "영업시간이 어떻게 되나요?", "answer": "평일 9시~18시입니다."}
  ]
}
```
**Response 202**
```json
{ "data": { "accepted": 1, "job_id": "job_faq_001" } }
```

> 적재 대상 테넌트는 **토큰의 company_id로 결정**. 다른 업체 FAQ에 적재 불가.

#### POST `/v1/admin/index` — 인덱싱 트리거
문서 인덱싱(파싱→청킹→임베딩→적재 + 질문 생성)을 비동기로 시작.

**Request**
```json
{ "source": "documents", "scope": "incremental" }  // scope: full | incremental
```
**Response 202** `{ "data": { "job_id": "job_idx_001" } }`

---

### 3.7 GET `/v1/health` — 헬스체크

인증 불필요. 의존 서비스 상태 포함.
```json
{
  "data": {
    "status": "ok",            // postgres/redis/vector_db 모두 ok && llm ok 이면 ok, 아니면 degraded
    "dependencies": {
      "postgres": "ok",
      "redis": "ok",
      "vector_db": "ok",
      "llm": "ok"             // 또는 "not_configured" (LLM 미설정 — FAQ/검색은 동작, 생성만 폴백)
    }
  }
}
```

> `llm: not_configured` 면 status 는 `degraded`(코어 DB 가 ok 여도). LLM 은 외부 호출 없이 키/CLI 설정 여부만 본다.

---

## 4. 레이트리밋

| 대상 | 기본 한도 |
|---|---|
| `/v1/chat`, `/v1/chat/sync` | **IP/세션당** 분당 N회 |
| `/v1/autocomplete` | **IP/세션당** 초당 M회(빈번하므로 별도 완화) |

초과 시 `429 RATE_LIMITED` + `Retry-After` 헤더.

> 비회원이라 사용자 식별이 없으므로 레이트리밋은 **IP/세션 기준**으로 적용한다(임의 `company_id` 입력에 의한 남용 방지). company_id별 집계도 병행.

---

## 5. 결정 필요사항

- [ ] 고객용: 비회원 + `company_id` 직접 수신 확정 (✔ 본 버전 반영). 유효 company_id 검증 방식(레지스트리 대조)
- [ ] 관리자 API 인증 방식(관리자 키/토큰) 및 권한 모델
- [ ] 스트리밍 방식: **SSE** vs WebSocket (현재 명세는 SSE 기준)
- [ ] 레이트리밋 구체 수치(IP/세션 기준)
- [ ] `session_id` 생성 주체(서버 발급 vs 클라이언트 생성) 및 추측 방지(난수성)
- [ ] 자동완성 시맨틱 보강 응답을 별도 엔드포인트로 둘지 여부
```
