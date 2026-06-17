"""업체별 FAQ MCP 서버 3개를 한 번에 기동한다 (A안, §08 §3).

각 서버는 streamable-http 로 독립 포트에 뜬다:
  pizza   → http://127.0.0.1:9001/mcp
  chinese → http://127.0.0.1:9002/mcp
  chicken → http://127.0.0.1:9003/mcp

실행: python scripts/run_faq_servers.py   (Ctrl+C 로 전체 종료)
개별 기동: python -m mcp_servers.faq_template.server --config <config>.yaml
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "mcp_servers" / "faq_template" / "config"
CONFIGS = ["faq_pizza.yaml", "faq_chinese.yaml", "faq_chicken.yaml"]


def main() -> None:
    procs: list[subprocess.Popen] = []
    for cfg in CONFIGS:
        path = CONFIG_DIR / cfg
        proc = subprocess.Popen(
            [sys.executable, "-m", "mcp_servers.faq_template.server", "--config", str(path)],
            cwd=str(ROOT),
        )
        procs.append(proc)
        print(f"started {cfg} (pid={proc.pid})", flush=True)

    print("FAQ 서버 3개 기동됨. Ctrl+C 로 종료.", flush=True)
    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        print("\n종료 중...", flush=True)
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    main()
