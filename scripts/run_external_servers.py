"""벤더 서버들을 한 번에 기동한다 (모노레포 통합판).

각 서버는 독립 배포 단위로, **자기 폴더의 `.venv`** 로 실행된다(독립 실행).
venv 가 없으면 먼저 만든다:  python scripts/setup_venvs.py

기동 대상(포트는 configs/tenants.yaml 과 일치):
  FAQ     : faq-pizza 9001 / faq-chinese 9002 / faq-chicken 9003 / faq-bunsik 9004
  일반     : general-pizza 9101 / general-chinese 9102 / general-chicken 9103 / general-bunsik 9104
  백엔드    : pizza-backend 9201  (general-pizza 의 메뉴/매장/배달/주문 도구가 호출)
  임베딩    : embedding-server 9300  (EMBEDDING_BACKEND=remote 일 때만 — 기본 hash 면 불필요)

실행: python scripts/run_external_servers.py            # 임베딩 서버 제외
      python scripts/run_external_servers.py --embedding # 임베딩 서버 포함
      (Ctrl+C 로 전체 종료)
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]  # scripts/ → 레포 루트(모노레포)

# 자식 서버 런타임 기본값 — 벤더 서버는 dotenv 를 안 읽으므로 런처가 환경변수로 주입한다.
# 셸에서 같은 변수를 export 하면 그 값이 우선한다(아래 {**DEFAULT_ENV, **os.environ}).
#   - remote: 중앙 임베딩 서버(9300) 호출로 임베딩 일관성 보장(hash 의 의역 매칭 한계 해소)
#   - FAQ_THRESHOLD=0.78: 의역 즉답은 살리고("몇시까지 영업해요?" 0.816) 오매칭은 차단("배달"↔"포장" 0.719)
DEFAULT_ENV = {
    "EMBEDDING_BACKEND": "remote",
    "EMBEDDING_SERVER_URL": "http://127.0.0.1:9300",
    "EMBEDDING_MODEL": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "EMBEDDING_DIM": "384",
    "FAQ_THRESHOLD": "0.78",
}

# 항상 기동: FAQ 4 + 일반 4 + 피자 백엔드
SERVERS = [
    "faq-pizza", "faq-chinese", "faq-chicken", "faq-bunsik",
    "general-pizza", "general-chinese", "general-chicken", "general-bunsik",
    "pizza-backend",
]
# 선택 기동(--embedding): 중앙 임베딩 서버 (EMBEDDING_BACKEND=remote 일 때만 필요)
OPTIONAL = ["embedding-server"]


def _python(project_dir: Path) -> Path | None:
    """프로젝트 전용 venv 인터프리터 경로(없으면 None)."""
    win = project_dir / ".venv" / "Scripts" / "python.exe"
    nix = project_dir / ".venv" / "bin" / "python"
    if win.exists():
        return win
    if nix.exists():
        return nix
    return None


def main() -> None:
    projects = list(SERVERS)
    if "--embedding" in sys.argv:
        projects += OPTIONAL

    # 셸 export 가 DEFAULT_ENV 보다 우선(개별 오버라이드 허용)
    child_env = {**DEFAULT_ENV, **os.environ}

    procs: list[subprocess.Popen] = []
    missing_venv: list[str] = []
    for name in projects:
        pdir = REPO_ROOT / name
        if not pdir.exists():
            print(f"[skip] {name} 폴더 없음: {pdir}", flush=True)
            continue
        py = _python(pdir)
        if py is None:
            missing_venv.append(name)
            print(f"[skip] {name} venv 없음 → python scripts/setup_venvs.py 먼저 실행", flush=True)
            continue
        proc = subprocess.Popen([str(py), "run.py"], cwd=str(pdir), env=child_env)
        procs.append(proc)
        print(f"started {name} (pid={proc.pid})", flush=True)

    if missing_venv:
        print(f"\n⚠️  venv 미설치: {', '.join(missing_venv)} — 위 서버는 기동되지 않았다.", flush=True)
    print(f"\n벤더 서버 {len(procs)}개 기동됨. Ctrl+C 로 종료.", flush=True)

    try:
        for p in procs:
            p.wait()
    except KeyboardInterrupt:
        print("\n종료 중...", flush=True)
        for p in procs:
            p.terminate()


if __name__ == "__main__":
    main()
