# general-chinese

중국집 **일반(도메인) MCP 서버** (FastAPI + FastMCP) — 독립 배포 단위.
도메인 도구 7개(documents·store·order). 오케스트레이터는 `http://127.0.0.1:9102/mcp` 로 MCP 호출.
중국집 데이터만 보유. 메뉴/정책은 공유 Qdrant `documents`(company_id 필터).

```bash
python -m venv .venv && ./.venv/Scripts/python.exe -m pip install -e .
python run.py   # http://127.0.0.1:9102/mcp + /health
```
