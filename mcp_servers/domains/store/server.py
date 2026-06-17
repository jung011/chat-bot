"""store MCP 서버 진입점 (독립 배포 단위, §02 §5).

실행: python -m mcp_servers.domains.store.server   (stdio transport)
"""
from __future__ import annotations

from mcp_servers._shared.server_factory import build_server
from mcp_servers.domains.store.tools import TOOLS

mcp = build_server("store", TOOLS)

if __name__ == "__main__":
    mcp.run()
