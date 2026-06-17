"""모든 업체별 MCP 서버를 한 번에 기동한다 (A안, §08).

FAQ 서버 3개 + 일반(도메인) 서버 3개 = 총 6개 독립 프로세스(streamable-http):
  FAQ:    pizza 9001 / chinese 9002 / chicken 9003
  일반:   pizza 9101 / chinese 9102 / chicken 9103

실행: python scripts/run_mcp_servers.py   (Ctrl+C 로 전체 종료)
개별 기동:
  python -m mcp_servers.faq_template.server --config <faq_*.yaml>
  python -m mcp_servers.general.server      --config <general_*.yaml>
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAQ_DIR = ROOT / "mcp_servers" / "faq_template" / "config"
GEN_DIR = ROOT / "mcp_servers" / "general" / "config"

JOBS = [
    ("mcp_servers.faq_template.server", FAQ_DIR / "faq_pizza.yaml"),
    ("mcp_servers.faq_template.server", FAQ_DIR / "faq_chinese.yaml"),
    ("mcp_servers.faq_template.server", FAQ_DIR / "faq_chicken.yaml"),
    ("mcp_servers.general.server", GEN_DIR / "general_pizza.yaml"),
    ("mcp_servers.general.server", GEN_DIR / "general_chinese.yaml"),
    ("mcp_servers.general.server", GEN_DIR / "general_chicken.yaml"),
]


def main() -> None:
    procs: list[subprocess.Popen] = []
    for module, cfg in JOBS:
        proc = subprocess.Popen(
            [sys.executable, "-m", module, "--config", str(cfg)], cwd=str(ROOT)
        )
        procs.append(proc)
        print(f"started {module} ({cfg.name}) pid={proc.pid}", flush=True)

    print("MCP 서버 6개 기동됨 (FAQ 3 + 일반 3). Ctrl+C 로 종료.", flush=True)
    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        print("\n종료 중...", flush=True)
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    main()
