# faq-pizza

피자집 **FAQ MCP 서버** (FastAPI + FastMCP) — 독립 배포 단위.

질문을 업체 FAQ 와 시맨틱 매칭해 임계값 이상이면 즉답을 반환하는 MCP 도구(`match_faq`)를
제공한다. 오케스트레이터(chatBot-sample)는 `http://<host>:<port>/mcp` 로 표준 MCP
프로토콜(streamable-http)로 호출한다.

- **독립 프로젝트**: 자체 의존성(`pyproject.toml`) + 자체 venv. 다른 프로젝트 코드를 import 하지 않는다.
- 데이터: 공유 로컬 Qdrant 의 `faq_pizza` 컬렉션(업체별 컬렉션 격리).

## 설치 & 실행

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate  / macOS·Linux: source .venv/bin/activate
pip install -e .
cp .env.example .env   # 필요 시 값 수정

python run.py          # http://127.0.0.1:9001/mcp + /health
```

## 확인

```bash
curl http://127.0.0.1:9001/health
```

## 엔드포인트
- `POST /mcp` — MCP 프로토콜(streamable-http). 도구: `match_faq(question) → {matched, answer?, score, question?}`
- `GET /health` — Qdrant 연결 상태
