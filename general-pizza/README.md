# general-pizza

피자집 **일반(도메인) MCP 서버** (FastAPI + FastMCP) — 독립 배포 단위.

도메인 도구 7개를 제공한다:
- documents: `search_menu`, `search_policy` (공유 Qdrant `documents`, company_id 필터, Hybrid+Rerank)
- store: `get_business_hours`, `get_store_info`, `check_delivery_area` (자체 seed_data)
- order: `get_order_guide`, `estimate_delivery_time` (자체 seed_data)

오케스트레이터는 `http://127.0.0.1:9101/mcp` 로 MCP(streamable-http) 호출.

- **독립 프로젝트**: 자체 의존성 + 자체 venv. 다른 프로젝트 코드 import 안 함.
- 피자집 데이터만 보유(벤더 독립). 메뉴/정책은 공유 Qdrant `documents`(company_id 필터).

## 설치 & 실행
```bash
python -m venv .venv && ./.venv/Scripts/python.exe -m pip install -e .
python run.py   # http://127.0.0.1:9101/mcp + /health
```
