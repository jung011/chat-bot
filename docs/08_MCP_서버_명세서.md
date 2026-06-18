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
| 역할 | 질문 임베딩 → 업체 FAQ 벡터검색 → 임계값 매칭 → 즉답/통과 |
| 입력 | `{question}` |
| 출력 | `{matched: bool, answer?: string, score: float}` |
| 설정 | `company_id`, `vector_db`, `threshold` (config.yaml) |

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

---

## 6. 통신 규약

| 항목 | 내용 |
|---|---|
| 호출 주체 | 오케스트레이터(`app/mcp/client.py`) |
| company_id 전달 | **모든 도구 호출에 필수** (격리) |
| 에러 형식 | `{ "error": { "code", "message" } }` |
| 타임아웃/재시도 | 도구별 타임아웃, 멱등 도구만 재시도 |

> company_id는 오케스트레이터가 토큰에서 받아 도구 호출에 주입. 도구는 받은 company_id로 데이터 필터.

## 7. 도구 description 작성 규칙 (중요)

Tool RAG 검색 정확도 = description 품질. 규칙:
1. **언제 쓰는지** 명확히("~문의에 사용").
2. 사용자 표현을 포함("배달 가능", "배송 지역").
3. 다른 도구와 **구분되게**(중복 회피).
4. 한 도구 = 한 책임.

## 8. 결정 필요사항
- [ ] MCP 통신 방식/포트(표준 MCP 프로토콜 vs 내부 HTTP)
- [ ] 도메인 서버 분리 단위 최종 확정(store/order 통합 여부)
- [ ] FAQ 서버 인스턴스 배포 방식(상시 vs 스케일-투-제로)
- [ ] 도구 인덱싱(설명 임베딩) 자동화 시점
- [ ] 도구 테스트 방식 — LLM 호출 없이 루프 검증하는 **테스트 대역(스크립트형 모델 stub)** 도입 여부 → 향후 평가/테스트 문서(11)에서 확정
