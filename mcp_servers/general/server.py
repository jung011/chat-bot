"""업체별 일반(도메인) MCP 서버 진입점 (§08, A안 — 업체별 분리).

documents·store·order 의 모든 도메인 도구를 한 서버로 묶어 노출한다.
코드 1벌(도메인 tools.py 단일 소스) + config/general_<id>.yaml 설정만 다르게 →
업체별 독립 프로세스/포트로 기동한다(§01 §6).

오케스트레이터는 app/mcp/domain_client.py 로 해당 업체 서버에 MCP 프로토콜로
도구를 호출한다. 도구는 company_id 인자를 받아 데이터를 필터한다(테넌트 격리).

실행:
    python -m mcp_servers.general.server --config mcp_servers/general/config/general_pizza.yaml
또는 전체:
    python scripts/run_mcp_servers.py
"""
from __future__ import annotations

from pathlib import Path

import yaml

from mcp_servers._shared.server_factory import build_server
from mcp_servers.domains.documents.tools import TOOLS as DOC_TOOLS
from mcp_servers.domains.order.tools import TOOLS as ORDER_TOOLS
from mcp_servers.domains.store.tools import TOOLS as STORE_TOOLS

ALL_TOOLS = [*DOC_TOOLS, *STORE_TOOLS, *ORDER_TOOLS]
DEFAULT_CONFIG = Path(__file__).parent / "config" / "general_pizza.yaml"


def load_config(path: str) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def build(config: dict):
    return build_server(
        f"general-{config['company_id']}",
        ALL_TOOLS,
        host=config.get("host", "127.0.0.1"),
        port=int(config.get("port", 9101)),
    )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    config = load_config(args.config)
    server = build(config)
    print(
        f"[general-{config['company_id']}] streamable-http on "
        f"http://{config.get('host', '127.0.0.1')}:{config.get('port', 9101)}/mcp "
        f"(tools: {len(ALL_TOOLS)})",
        flush=True,
    )
    server.run(transport="streamable-http")


if __name__ == "__main__":
    main()
