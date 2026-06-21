# general-bunsik

분식집 **일반(도메인) MCP 서버** (FastAPI + FastMCP) — 독립 배포 단위.
도메인 도구 7개 + `ingest_documents`. 오케스트레이터는 `http://127.0.0.1:9104/mcp` 로 MCP 호출.
분식집 데이터만 보유. 문서는 공유 Qdrant `documents`(company_id 태깅). 연동 계약은 `docs/08 §9`.

```bash
python -m venv .venv && ./.venv/Scripts/python.exe -m pip install -e .
python run.py   # http://127.0.0.1:9104/mcp + /health
```
