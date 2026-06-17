"""FAQ 서버 진입점 (업체별 인스턴스 템플릿, §08 §3, A안).

코드 1벌 — config.yaml 만 바꿔 N개 인스턴스로 배포한다(§01 §6).
입력 {question} → 출력 {matched, answer?, score, question?}.

streamable-http 전송으로 기동하며, 업체별로 다른 host/port 에 독립 서버로 뜬다.
오케스트레이터는 app/mcp/faq_client.py 로 이 서버에 MCP 프로토콜로 연결한다.

실행:
    python -m mcp_servers.faq_template.server --config mcp_servers/faq_template/config/faq_pizza.yaml
또는 3개 한 번에:
    python scripts/run_faq_servers.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml
from mcp.server.fastmcp import FastMCP

from mcp_servers._shared.responses import ok
from mcp_servers.faq_template import matcher

DEFAULT_CONFIG = Path(__file__).parent / "config" / "faq_pizza.yaml"


def load_config(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def build_server(config: dict) -> FastMCP:
    mcp = FastMCP(
        f"faq-{config['company_id']}",
        host=config.get("host", "127.0.0.1"),
        port=int(config.get("port", 9001)),
    )

    async def match_faq(question: str) -> dict:
        """질문을 업체 FAQ 와 시맨틱 매칭한다. 임계값 이상이면 즉답을 반환."""
        m = await matcher.match(
            question,
            collection=config["collection"],
            company_id=config["company_id"],
            threshold=float(config.get("threshold", 0.85)),
        )
        return ok(matched=m.matched, answer=m.answer, score=m.score, question=m.question)

    mcp.add_tool(match_faq, name="match_faq", description="업체 FAQ 시맨틱 인터셉트")
    return mcp


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    config = load_config(args.config)
    server = build_server(config)
    print(
        f"[faq-{config['company_id']}] streamable-http on "
        f"http://{config.get('host', '127.0.0.1')}:{config.get('port', 9001)}/mcp",
        flush=True,
    )
    server.run(transport="streamable-http")


if __name__ == "__main__":
    main()
