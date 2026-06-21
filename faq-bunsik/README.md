# faq-bunsik

분식집 **FAQ MCP 서버** (FastAPI + FastMCP) — 독립 배포 단위.
`match_faq`·`upsert_faq` 도구 제공. 오케스트레이터는 `http://127.0.0.1:9004/mcp` 로 MCP 호출.
데이터는 공유 Qdrant `faq_bunsik`. 연동 계약은 상위 chatBot-sample `docs/08 §9` 참고.

```bash
python -m venv .venv && ./.venv/Scripts/python.exe -m pip install -e .
python run.py   # http://127.0.0.1:9004/mcp + /health
```
