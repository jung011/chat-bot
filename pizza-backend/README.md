# pizza-backend

피자집 **백엔드 API**(FastAPI + PostgreSQL). 업체가 웹/앱 서비스를 위해 운용하는
일반적인 백엔드를 표현한다. 메뉴·가격·매장·배달·주문 등 **정형/실시간 데이터의 단일
진실 공급원(SSOT)** 이다.

- MCP 일반 서버(general-pizza)는 이 **API 를 HTTP 로 호출**해 데이터를 가져온다
  (DB 직접 접근 대신 — 비즈니스 로직/검증/권한 재사용).
- DB 는 오케스트레이터 메타DB(`app`)와 분리된 **업체 전용 DB(`pizza_shop`)** 사용.

## 실행
```bash
# Postgres 컨테이너에 pizza_shop DB 가 있어야 함:
#   docker exec postgres createdb -U postgres pizza_shop
python run.py          # http://127.0.0.1:9201 (PG_*/PORT 환경변수로 조정)
```

## 엔드포인트
| 메서드 | 경로 | 용도 |
|---|---|---|
| GET | `/health` | 헬스체크 |
| GET | `/menu?query=&category=` | 메뉴/가격 검색 |
| GET | `/store` | 매장정보(영업시간·연락처·주차·주문안내) |
| GET | `/delivery/check?address=` | 배달 가능 지역 확인 |
| GET | `/delivery/estimate?area=` | 예상 배달 소요시간 |
| GET | `/orders/{order_id}` | 주문 상태 조회(라이브) |

## DB 접속(환경변수)
`PG_HOST`(localhost) · `PG_PORT`(5432) · `PG_USER`(postgres) · `PG_PASSWORD`(postgres) · `PG_DB`(pizza_shop)
