"""FAQ 서버 진입점 (업체별 인스턴스 템플릿, §08 §3).

코드 1벌 — config.yaml 만 바꿔 N개 인스턴스로 배포한다(§01 §6).
입력 {question} → 출력 {matched, answer?, score}.

실행: python -m mcp_servers.faq_template.server --config <company>.yaml
(파일럿은 오케스트레이터가 matcher.match() 를 인프로세스로 호출하므로
 상시 서버 기동은 선택사항. 본 모듈은 A안 인스턴스 분리 시 배포 단위가 된다.)
"""
from __future__ import annotations

from pathlib import Path

import yaml
from mcp.server.fastmcp import FastMCP

from mcp_servers._shared.responses import ok
from mcp_servers.faq_template import matcher


def load_config(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def build_server(config: dict) -> FastMCP:
    mcp = FastMCP(f"faq-{config['company_id']}")

    async def match_faq(question: str) -> dict:
        """질문을 업체 FAQ 와 시맨틱 매칭한다. 임계값 이상이면 즉답을 반환."""
        m = await matcher.match(
            question,
            collection=config["collection"],
            company_id=config["company_id"],
            threshold=float(config.get("threshold", 0.85)),
        )
        return ok(matched=m.matched, answer=m.answer, score=m.score)

    mcp.add_tool(match_faq, name="match_faq", description="업체 FAQ 시맨틱 인터셉트")
    return mcp


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(Path(__file__).with_name("config.example.yaml")))
    args = parser.parse_args()
    build_server(load_config(args.config)).run()
