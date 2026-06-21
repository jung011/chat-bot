# faq-chinese

중국집 **FAQ MCP 서버** (FastAPI + FastMCP) — 독립 배포 단위.
`match_faq` 도구로 중국집 FAQ 를 시맨틱 매칭. 오케스트레이터는 `http://127.0.0.1:9002/mcp`
로 MCP(streamable-http) 호출. 데이터는 공유 Qdrant `faq_chinese`.

```bash
python -m venv .venv && ./.venv/Scripts/python.exe -m pip install -e .
python run.py   # http://127.0.0.1:9002/mcp + /health
```
