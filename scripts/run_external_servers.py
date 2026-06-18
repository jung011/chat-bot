"""외부 MCP 서버 6개를 한 번에 기동한다 (A안 — 독립 프로젝트).

상위 git/ 폴더의 형제 프로젝트들을 각자의 venv 로 실행한다:
  FAQ:  faq-pizza 9001 / faq-chinese 9002 / faq-chicken 9003
  일반: general-pizza 9101 / general-chinese 9102 / general-chicken 9103

각 프로젝트는 독립 배포 단위(자체 의존성/venv). 본 스크립트는 로컬 개발 편의용 런처일 뿐,
실제 운영에선 각 서비스가 별도 호스트/컨테이너로 배포된다.

실행: python scripts/run_external_servers.py   (Ctrl+C 로 전체 종료)
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

GIT_ROOT = Path(__file__).resolve().parents[2]  # chatBot-sample/scripts → git/
PROJECTS = [
    "faq-pizza", "faq-chinese", "faq-chicken",
    "general-pizza", "general-chinese", "general-chicken",
]


def _python(project_dir: Path) -> str:
    win = project_dir / ".venv" / "Scripts" / "python.exe"
    nix = project_dir / ".venv" / "bin" / "python"
    return str(win if win.exists() else nix)


def main() -> None:
    procs: list[subprocess.Popen] = []
    for name in PROJECTS:
        pdir = GIT_ROOT / name
        if not pdir.exists():
            print(f"[skip] {name} 프로젝트 폴더 없음: {pdir}", flush=True)
            continue
        py = _python(pdir)
        proc = subprocess.Popen([py, "run.py"], cwd=str(pdir))
        procs.append(proc)
        print(f"started {name} (pid={proc.pid})", flush=True)

    print(f"외부 MCP 서버 {len(procs)}개 기동됨. Ctrl+C 로 종료.", flush=True)
    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        print("\n종료 중...", flush=True)
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    main()
