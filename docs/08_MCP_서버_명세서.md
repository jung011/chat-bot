# MCP 서버 명세서

> **대상:** 백엔드 개발팀
> **목적:** MCP 서버(도구 제공자)의 종류·도구 카탈로그·통신 규약·작성 규칙을 정의한다.
> **관련 문서:** [01_아키텍처_설계서.md](./01_아키텍처_설계서.md) · [02_백엔드_패키지구조.md](./02_백엔드_패키지구조.md) (mcp_servers/, app/mcp/) · [09_멀티테넌시_업체온보딩_가이드.md](./09_멀티테넌시_업체온보딩_가이드.md)
> **상태:** 초안 (v1)

> ⚠️ **구현 현황(as-built):** [12_구현_아키텍처.md](./12_구현_아키텍처.md) 참고. 주요 차이:
> - **MCP 서버 = 외부 독립 프로젝트**(상위 `git/`): `faq-{pizza,chinese,chicken}`(9001~3), `general-{pizza,chinese,chicken}`(9101~3). 각자 **FastAPI + FastMCP 마운트**(streamable-http, `/mcp`+`/health`), 자체 pyproject/venv/코드.
> - 일반 서버는 documents·store·order 도구 **7개를 한 서버로** 묶음(서버별 분리 아님).
> - **적재 도구 추가**: faq 서버 `upsert_faq`, 일반 서버 `ingest_documents`(데이터 소유=벤더). 이 둘은 Tool RAG 후보에서 제외.
> - 오케스트레이터는 `app/mcp/{faq_client,domain_client}` 로 **원격 전용** 호출(인프로세스 폴백/레지스트리 없음).
> - 도구 카탈로그는 정적 파일 없이 **`list_tools` 디스커버리**(`scripts/index_tools.py`).

---

## 1. 원칙

- **MCP 서버는 LLM이 아니다.** 도구(함수)를 표준 인터페이스로 노출하는 제공자다(§01 §3 원칙2).
- LLM은 오케스트레이터에만 있다. MCP 서버는 입력→처리→결과 반환만.
- 서버는 도메인/업체 경계로 분리(코드·배포·권한).

## 2. 서버 종류

| 서버 | 분류 | 격리 | LLM |
|---|---|---|---|
| FAQ 서버(템플릿) | 업체별 인스턴스 | **인스턴스 격리(A안)** | ❌ |
| 문서(documents) | 도메인, 중앙 | company_id 필터 | ❌ |
| 매장정보(store) | 도메인, 중앙 | company_id 필터 | ❌ |
| 주문안내(order) | 도메인, 중앙 | company_id 필터 | ❌ |

> 파일럿에서 주문/결제는 **안내까지만**(실제 트랜잭션 제외, §05 Out of Scope).

## 3. FAQ 서버 템플릿 (업체별)

**코드 1벌, 설정만 다르게**(§01 §6). 업체 인스턴스로 배포.

| 항목 | 내용 |
|---|---|
| 역할 | 질문 임베딩 → 업체 FAQ 벡터검색 → ① 임계값 즉답(`match_faq`) / ② top-K 후보(`search_faq`) |
| 입력 | `{question}` (+ `search_faq` 는 `top_k`) |
| 출력 | `match_faq`: `{matched, answer?, score}` · `search_faq`: `{results:[{question,answer,score}]}` |
| 설정 | `company_id`, `embedding_backend/model`, `faq_threshold` (환경변수) |

> **두 가지 쓰임(정공법)**: `match_faq` 는 0단계 즉답(단일 질문 빠른 처리), `search_faq` 는 임계값 없이
> 후보를 돌려줘 rag/agent 가 문서·도구와 **병합**한다. 복합 질문(예: "주차+마르게리따 가격")에서 FAQ-전용
> 정보가 누락되지 않게 한다. 오케스트레이터는 복합 질문이면 0단계 즉답을 건너뛰고(한쪽만 답하는 오즉답 방지)
> rag/agent 로 보내 `search_faq` 로 다건을 함께 답한다.

**config 예시**
```yaml
company_id: pizza
vector_db: "qdrant-pizza:6333"
collection: faq
threshold: 0.85
```

## 4. 도메인 MCP 도구 카탈로그

> Tool RAG가 검색하는 대상. **description이 검색 품질을 좌우**하므로 정성껏 작성(§01 §4.4).

### 4.1 documents 서버

| 도구 | 설명 | params |
|---|---|---|
| `search_menu` | 메뉴/가격/옵션을 검색한다 | `query: str`, `company_id: str` |
| `search_policy` | 배달지역/배달비/최소주문 등 정책을 검색한다 | `query: str`, `company_id: str` |

### 4.2 store 서버

| 도구 | 설명 | params |
|---|---|---|
| `get_business_hours` | 영업시간/휴무일을 조회한다 | `company_id: str` |
| `get_store_info` | 위치/주차/연락처를 조회한다 | `company_id: str` |
| `check_delivery_area` | 특정 지역 배달 가능 여부를 확인한다 | `company_id: str`, `address: str` |

### 4.3 order 서버 (안내용)

| 도구 | 설명 | params |
|---|---|---|
| `get_order_guide` | 주문 방법/결제수단을 안내한다 | `company_id: str` |
| `estimate_delivery_time` | 예상 배달 소요시간을 안내한다 | `company_id: str`, `area?: str` |

### 4.4 도구 정의 스키마 (Tool RAG 인덱싱용)
```jsonc
{
  "server": "store",
  "name": "check_delivery_area",
  "description": "특정 주소가 배달 가능 지역인지 확인한다. 배달/배송 가능 여부 문의에 사용.",
  "params_schema": {
    "type": "object",
    "properties": {
      "company_id": {"type": "string"},
      "address": {"type": "string"}
    },
    "required": ["company_id", "address"]
  }
}
```

---

## 5. 함수(도구) 명세

MCP 도구 = 함수다. 각 함수는 아래 표준에 따라 구현·문서화한다.

### 5.1 반환 포맷 표준 (ok / fail)

모든 도구는 **일관된 dict**를 반환한다. 직접 dict를 만들지 말고 헬퍼를 사용한다.

```python
# mcp_servers/_shared/responses.py
def ok(**data):    return {"success": True, **data}
def fail(message): return {"success": False, "message": message}
```

| 케이스 | 형태 |
|---|---|
| 성공 | `{"success": true, ...데이터}` |
| 실패/빈 결과 | `{"success": false, "message": "사람이 읽을 수 있는 사유"}` |

> 모델(오케스트레이터)은 이 결과를 받아 사람 말로 서술한다. `fail`의 `message`는 사용자에게 그대로 전달될 수 있으므로 명확하고 정중하게 작성한다.

### 5.2 구현 패턴 (FastMCP)

`@mcp.tool()` 데코레이터가 **함수 시그니처 + 타입힌트 + docstring**에서 도구 스키마를 자동 생성한다(별도 명세 JSON·디스패처 불필요).

```python
@mcp.tool()
def check_delivery_area(company_id: str, address: str) -> dict:
    """특정 주소가 배달 가능 지역인지 확인한다. 배달/배송 가능 여부 문의에 사용."""
    # 1) 인자 검증 → 2) 데이터 조회(company_id 필터) → 3) ok/fail 반환
    ...
```

규칙:
- **docstring = description** → §6 작성 규칙을 따른다(Tool RAG 검색 품질 직결).
- **company_id 파라미터 필수** → 도구 내부에서 반드시 필터(테넌트 격리).
- **인자 검증** → 모델이 잘못된 인자를 줄 수 있으므로 실행 전 검증, 위반 시 `fail()`.

### 5.3 함수 명세 템플릿

각 도구는 아래 항목을 채운다.

```
#### <도구명>  (server: <서버>)
- 목적:        한 문장(언제 쓰는지)
- description: Tool RAG 인덱싱용 설명(§7 규칙)
- 파라미터:    이름 / 타입 / 필수 / 설명
- 반환(성공):  ok(...) 필드
- 반환(실패):  fail 사유 케이스들
- 부작용:      읽기전용 여부(멱등성), 재시도 가능 여부
- 예시:        입력 → 출력
```

### 5.4 도구별 상세 명세

#### search_menu  (server: documents)
- 목적: 메뉴/가격/옵션을 검색해 반환한다.
- description: "메뉴 이름·가격·옵션·세트 구성을 검색한다. 메뉴/가격/구성 문의에 사용."
- 파라미터: `company_id`(str, 필수) / `query`(str, 필수, 검색어)
- 반환(성공): `ok(items=[{name, price, options, set}], count)`
- 반환(실패): `fail("관련 메뉴를 찾지 못했습니다.")`
- 부작용: 읽기전용(멱등), 재시도 가능
- 예시: `{company_id:"pizza", query:"마르게리따 가격"}` → `ok(items=[{name:"마르게리따 L", price:25000, ...}], count=1)`

#### search_policy  (server: documents)
- 목적: 배달지역/배달비/최소주문 등 정책 텍스트를 검색한다.
- description: "배달지역·배달비·최소주문금액·환불 등 정책을 검색한다. 정책 문의에 사용."
- 파라미터: `company_id`(str, 필수) / `query`(str, 필수)
- 반환(성공): `ok(snippets=[{title, text, source}], count)`
- 반환(실패): `fail("관련 정책 정보를 찾지 못했습니다.")`
- 부작용: 읽기전용, 재시도 가능

#### get_business_hours  (server: store)
- 목적: 영업시간/휴무일을 조회한다.
- description: "영업시간·브레이크타임·휴무일을 조회한다. 영업시간 문의에 사용."
- 파라미터: `company_id`(str, 필수)
- 반환(성공): `ok(hours=[{day, open, close}], holidays=[...])`
- 반환(실패): `fail("영업시간 정보가 등록되지 않았습니다.")`
- 부작용: 읽기전용, 재시도 가능

#### get_store_info  (server: store)
- 목적: 위치/주차/연락처 등 매장 기본정보를 조회한다.
- description: "매장 위치·주차·전화번호 등 기본 정보를 조회한다. 위치/연락처 문의에 사용."
- 파라미터: `company_id`(str, 필수)
- 반환(성공): `ok(address, phone, parking, map_url)`
- 반환(실패): `fail("매장 정보가 등록되지 않았습니다.")`
- 부작용: 읽기전용, 재시도 가능

#### check_delivery_area  (server: store)
- 목적: 특정 주소가 배달 가능 지역인지 확인한다.
- description: "특정 주소가 배달 가능 지역인지 확인한다. 배달/배송 가능 여부 문의에 사용."
- 파라미터: `company_id`(str, 필수) / `address`(str, 필수)
- 반환(성공): `ok(deliverable=true|false, fee, min_order, eta_min)`
- 반환(실패): `fail("해당 주소의 배달 지역 정보를 찾을 수 없습니다.")`
- 부작용: 읽기전용, 재시도 가능
- 예시: `{company_id:"chicken", address:"서울시 ..."}` → `ok(deliverable=true, fee=3000, min_order=15000, eta_min=35)`

#### get_order_guide  (server: order)
- 목적: 주문 방법/결제수단을 안내한다(실제 주문 처리는 범위 밖).
- description: "주문 방법·결제수단을 안내한다. 주문/결제 방법 문의에 사용."
- 파라미터: `company_id`(str, 필수)
- 반환(성공): `ok(channels=[...], payment_methods=[...], notes)`
- 반환(실패): `fail("주문 안내 정보가 등록되지 않았습니다.")`
- 부작용: 읽기전용, 재시도 가능

#### estimate_delivery_time  (server: order)
- 목적: 예상 배달 소요시간을 안내한다.
- description: "예상 배달 소요시간을 안내한다. 배달 시간 문의에 사용."
- 파라미터: `company_id`(str, 필수) / `area`(str, 선택)
- 반환(성공): `ok(eta_min, peak=true|false)`
- 반환(실패): `fail("배달 시간 정보를 산출할 수 없습니다.")`
- 부작용: 읽기전용, 재시도 가능

### 5.5 새 도구 추가 절차 (FastMCP 기준)

samplepkg의 "3군데 수정"이 MCP에선 간소화된다.

| 단계 | 작업 |
|---|---|
| 1 | 해당 서버에 `@mcp.tool()` 함수 구현(+`ok/fail`) — 스키마/디스패치 자동 |
| 2 | docstring을 §7 규칙에 맞게 작성 |
| 3 | Tool RAG 인덱스에 도구 description 임베딩 재적재 |
| 4 | 본 문서 §5.4에 명세 추가 |

### 5.6 적재/관리 도구 (as-built — 데이터 소유=벤더)

데이터 적재를 벤더 서버가 소유한다. 아래 도구는 **고객 질의용이 아니므로 Tool RAG 후보에서 제외**(`index_tools.py` denylist).

#### match_faq  (server: faq-<id>)
- 목적: 질문을 업체 FAQ 와 시맨틱 매칭(0단계 인터셉트, §3).
- 파라미터: `question`(str, 필수)  ※ 임계값/컬렉션은 서버 config 소유
- 반환: `{matched: bool, answer?, question?, score}`
- 호출: 오케스트레이터 `faq_client`

#### upsert_faq  (server: faq-<id>)
- 목적: 업체 FAQ 를 적재(임베딩→자기 `faq_<id>` 컬렉션). 결정적 ID(질문 해시)로 멱등.
- 파라미터: `company_id`(str, 인터페이스용) / `items`(list, [{question, answer, category?}])
- 반환: `ok(accepted=<int>)`
- 호출: 오케스트레이터 `POST /v1/admin/faq` → 위임, 또는 벤더 직접

#### ingest_documents  (server: general-<id>)
- 목적: 업체 문서를 청킹+임베딩해 공유 `documents` 컬렉션에 적재(company_id 태깅). 결정적 ID 로 멱등.
- 파라미터: `company_id`(str, 인터페이스용) / `docs`(list, [{doc_id, title, category, text, source_uri}])
- 반환: `ok(chunks=<int>)`
- 호출: 오케스트레이터 seed / 벤더 직접

---

## 6. 통신 규약 (as-built)

| 항목 | 내용 |
|---|---|
| **전송/프로토콜** | **MCP over streamable-http (HTTP)**. 각 업체 서버가 `/mcp` 로 노출(+`/health` REST). FAQ 9001~3 / 일반 9101~3 |
| 호출 주체 | 오케스트레이터의 `app/mcp/faq_client.py`(FAQ) · `domain_client.py`(도메인) — **원격 전용**(인프로세스 폴백/레지스트리 없음) |
| 도구 발견 | `scripts/index_tools.py` 가 일반 서버 `list_tools` 로 디스커버리 → Tool RAG(`tools`) 적재. 정적 카탈로그 없음 |
| company_id 전달 | **모든 도구 호출에 필수**. 비회원 구조라 **요청 body/query 의 company_id**(§03 §1.2)를 받아 주입. 적재 도구는 서버가 자기 config 의 company_id 사용 |
| 결과 형식 | 도구는 ok/fail dict(§5.1) 반환 → MCP 전송 시 `structuredContent` 또는 `content[].text`(JSON)로 래핑. 클라이언트가 둘 다 파싱 |
| 에러 형식 | **두 층위**: ① 도구층 = `fail()` → `{success:false, message}`(§5.1) · ② API층 = 공통 envelope `{error:{code,message,details}}`(§03 §1.3). MCP 전송 오류는 클라이언트가 잡아 처리 |
| 타임아웃/재시도 | 클라이언트 타임아웃(FAQ 5s / 도메인 10s), 멱등(읽기) 도구만 재시도. 서버 미가동 시 FAQ→통과(rag), 도메인→답변 실패 |

> 통신 경로는 인프로세스가 아니라 **HTTP(streamable-http)** 다 — 업체 서버가 외부 독립 프로세스이기 때문(§02 as-built, [12](./12_구현_아키텍처.md) §4).

## 7. 도구 description 작성 규칙 (중요)

Tool RAG 검색 정확도 = description 품질. 규칙:
1. **언제 쓰는지** 명확히("~문의에 사용").
2. 사용자 표현을 포함("배달 가능", "배송 지역").
3. 다른 도구와 **구분되게**(중복 회피).
4. 한 도구 = 한 책임.

## 8. 결정 필요사항 (현황)
- [x] MCP 통신 방식/포트 → **streamable-http(HTTP)**, FAQ 9001~3 / 일반 9101~3 (`/mcp`)
- [x] 도메인 서버 분리 단위 → **업체별 "일반 서버" 1개에 documents·store·order 도구 통합**
- [x] 도구 인덱싱 자동화 → `scripts/index_tools.py` 가 `list_tools` 디스커버리로 적재
- [x] 도구 테스트(LLM 없이) → 테스트는 `anthropic` 고정(키 없음→degrade)로 결정적. 도구 자체 테스트는 외부 벤더 프로젝트 소유
- [ ] FAQ/일반 서버 배포 방식(상시 vs 스케일-투-제로) — 미정

---

## 9. 벤더 연동 계약 (Integration Contract) — 신규 서버 개발 시 필독

> 신규 업체가 **오케스트레이터와 실제로 맞물리는** 서버를 만들려면 아래를 **반드시** 지킨다.
> (언어·내부 구현·질의 도구 구성은 자유지만, 이 계약은 고정이다. 온보딩 절차는 [09](./09_멀티테넌시_업체온보딩_가이드.md).)

### 9.1 전송 & 엔드포인트
- **MCP over streamable-http**, 경로 **`/mcp`** (FastAPI 에 FastMCP 마운트 또는 FastMCP standalone).
- **`/health`** (REST GET) 권장 — 런처/헬스체크용: `{"data":{"status":"ok", ...}}`.
- 오케스트레이터는 `configs/tenants.yaml` 의 `faq.server_url` / `general_server_url` 로 연결한다.

### 9.2 필수 고정 도구 (이름·시그니처·반환을 정확히 일치)
오케스트레이터가 **도구 이름을 하드코딩**해 부르므로 아래는 정확히 맞춰야 한다.

**FAQ 서버**
| 도구 | 시그니처 | 반환 |
|---|---|---|
| `match_faq` | `(question: str)` | `{matched: bool, answer?, question?, score: float}` — 0단계 즉답(임계값 이상 1건) |
| `search_faq` | `(question: str, top_k: int = 5)` | `{results: [{question, answer, score}]}` — 임계값 없는 top-K(생성 컨텍스트용) |
| `upsert_faq` | `(company_id: str, items: [{question, answer, category?}])` | `ok(accepted: int)` |

> `search_faq` 는 복합 질문 대응의 핵심이다. 오케스트레이터 rag/agent 경로가 **임계값 없이** 후보 top-K 를
> 받아 문서·도구 결과와 **병합**한다(§3 정공법). `match_faq` 는 단일 질문의 빠른 즉답(0단계)용으로 별도 유지.

**일반 서버**
| 도구 | 시그니처 | 반환 |
|---|---|---|
| `ingest_documents` | `(company_id: str, docs: [{doc_id, title, category, text, source_uri}])` | `ok(chunks: int)` |
| **질의 도구**(search_menu 등) | **자유** — 단 `company_id` 인자 + ok/fail | ok/fail |

> 질의 도구는 **이름·개수 자유**: `list_tools` 디스커버리로 발견되고 description(§7) 품질로 매칭된다. 단 모든 도구는 **`company_id` 인자 필수**.

### 9.3 임베딩 규약 (필수) — ⚠️ 임베딩 일관성

임베더는 **백엔드 선택식**이다(환경변수 `EMBEDDING_BACKEND`):
- **`hash`**(기본): `HashEmbedder`, dim 384 — 토큰화 `[0-9A-Za-z가-힣]+`(소문자), sha1 2-버킷 가산, L2 정규화. 의존성·키 불필요(데모/오프라인).
- **`fastembed`**: 로컬 ONNX 실제 임베딩 모델(API 키 불필요). 파일럿 모델 `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`(dim 384) — 한국어 의미 유사도 확보(조사/어형 변화에 강함).

**(A) 일반 서버 — 강제 일치(hard):** 공유 `documents` 컬렉션을 오케스트레이터와 함께 쓰므로
**backend·model·dim 을 오케스트레이터와 100% 동일**하게 맞춰야 한다. 불일치 시 질의 벡터와 저장 벡터가
직교(코사인 ≈ 0)해 **문서검색이 전부 깨진다.** (또는 벤더별 `documents` 컬렉션 분리로 완전 독립화 — 택1)

**(B) FAQ 서버 — 내부 일치 + 점수 분포 정합:**
- `faq_<id>` 는 자기만 읽고/쓰지만, **적재(ingest)와 검색(match/search)이 반드시 동일 임베더**여야 한다.
  ⚠️ 흔한 함정: 적재는 `hash`, 검색은 `fastembed` 처럼 어긋나면 같은 컬렉션 안에서도 코사인 ≈ 0 → **검색 0건**.
  서버 내부 모든 임베딩 경로를 단일 `get_embedder()` 로 통일할 것.
- 오케스트레이터는 `search_faq` 점수에 **고정 floor(0.3)** 를 적용한다. floor 는 `fastembed`(관련 0.48~0.92,
  무관 ~0.16) 분포 기준이므로, **시스템과 같은 backend/model 사용을 권장**(다른 모델이면 점수 분포가 달라
  floor 가 오작동할 수 있음).

> 요약: documents(일반 서버)는 **반드시** 동일, faq(FAQ 서버)는 **내부 일치 필수 + 시스템과 동일 모델 권장**.
> dim 은 hash·파일럿 fastembed 모두 384 로 동일하지만, **모델이 다르면 벡터 호환 불가**(재색인 필요).

### 9.4 데이터 스키마 (공유 컬렉션)
- `documents` payload: `{company_id, doc_id, chunk_index, text, title, category, source_uri}`. 오케스트레이터 rag 가 `text/title/category` 를 읽고 `company_id` 로 필터(§04 §3.2).
- 포인트 ID 는 **결정적**(재적재 멱등). 문자열 ID 는 **UUID5(고정 네임스페이스 `00000000-0000-0000-0000-000000000abc`)** 로 변환 — 오케스트레이터와 동일 규칙.
- 모든 적재에 **`company_id` 태깅**(격리).

### 9.5 결과·에러 형식
- 도구는 ok/fail dict 반환(§5.1). FastMCP 가 `structuredContent`(+`content[].text` JSON)로 래핑 → 오케스트레이터가 둘 다 파싱.
- 적재/관리 도구(`upsert_faq`·`ingest_documents`)는 오케스트레이터 `index_tools` 에서 **Tool RAG 후보 제외**(denylist) — 벤더는 신경 쓸 필요 없음.

### 9.6 온보딩 후 자가 검증
- `match_faq("등록한 FAQ 질문")` → 즉답(matched=true) 반환?
- `search_faq("등록한 FAQ 질문")` → 후보 top-K 에 해당 FAQ 가 **점수 0.3 이상**으로 포함?
  (적재≠검색 임베더 불일치면 점수 ≈ 0 으로 나옴 — §9.3 함정)
- `ingest_documents(docs)` 적재 후, 오케스트레이터 rag 질의가 그 문서로 답하나?(임베딩 일치 확인)
- 타 `company_id` 데이터가 섞여 나오지 않나?(격리)
