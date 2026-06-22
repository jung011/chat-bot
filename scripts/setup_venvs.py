"""각 프로젝트(오케스트레이터 + 벤더 서버)에 독립 venv 를 만든다.

시스템 기본 python 이 3.9 라도, **Python 3.11 인터프리터**로 각 폴더에 `.venv` 를
생성하고 editable 설치한다. 우선 `uv`(빠름)를 쓰고, 없으면 `venv + pip` 로 폴백한다.

실행:
    python scripts/setup_venvs.py                 # 오케스트레이터 + 서버 9개
    python scripts/setup_venvs.py --embedding     # embedding-server 까지
    python scripts/setup_venvs.py --fastembed     # 임베딩 모델(ONNX) extras 까지 설치
    PYTHON=3.11 python scripts/setup_venvs.py      # 사용할 파이썬 버전 지정(기본 3.11)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PY_VERSION = os.getenv("PYTHON", "3.11")

# (폴더, extras) — extras 는 pip 익스트라(예: ["dev"]). 루트(".")는 오케스트레이터.
TARGETS: list[tuple[str, list[str]]] = [
    (".", ["dev"]),
    ("faq-pizza", []), ("faq-chinese", []), ("faq-chicken", []), ("faq-bunsik", []),
    ("general-pizza", []), ("general-chinese", []), ("general-chicken", []), ("general-bunsik", []),
    ("pizza-backend", []),
]
OPTIONAL: list[tuple[str, list[str]]] = [("embedding-server", [])]

USE_UV = shutil.which("uv") is not None


def _run(cmd: list[str]) -> None:
    print("  $", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def _venv_python(pdir: Path) -> Path:
    win = pdir / ".venv" / "Scripts" / "python.exe"
    return win if sys.platform == "win32" else pdir / ".venv" / "bin" / "python"


def setup(folder: str, extras: list[str], want_fastembed: bool) -> None:
    pdir = (REPO_ROOT / folder).resolve()
    if not (pdir / "pyproject.toml").exists():
        print(f"[skip] {folder}: pyproject.toml 없음 ({pdir})", flush=True)
        return

    # extras 조합: [dev] + (--fastembed 시 fastembed extra 가 있는 프로젝트만)
    eff = list(extras)
    if want_fastembed and (pdir / "pyproject.toml").read_text(encoding="utf-8").find("fastembed = ") != -1:
        eff.append("fastembed")
    spec = f"{pdir}[{','.join(eff)}]" if eff else str(pdir)

    print(f"\n=== {folder} (python {PY_VERSION}, extras={eff or '-'}) ===", flush=True)
    venv = pdir / ".venv"

    if USE_UV:
        _run(["uv", "venv", "--python", PY_VERSION, str(venv)])
        _run(["uv", "pip", "install", "--python", str(_venv_python(pdir)), "-e", spec])
    else:
        py = shutil.which(f"python{PY_VERSION}") or shutil.which("python3.11")
        if not py:
            print(f"[error] python{PY_VERSION} 인터프리터를 찾을 수 없음. uv 설치 또는 pyenv 사용 권장.", flush=True)
            sys.exit(1)
        _run([py, "-m", "venv", str(venv)])
        _run([str(_venv_python(pdir)), "-m", "pip", "install", "-U", "pip"])
        _run([str(_venv_python(pdir)), "-m", "pip", "install", "-e", spec])


def main() -> None:
    targets = list(TARGETS)
    if "--embedding" in sys.argv:
        targets += OPTIONAL
    want_fastembed = "--fastembed" in sys.argv

    print(f"venv 설치 시작 — 도구: {'uv' if USE_UV else 'venv+pip'}, python {PY_VERSION}", flush=True)
    for folder, extras in targets:
        setup(folder, extras, want_fastembed)
    print("\n✅ 완료. 서버 기동:  python scripts/run_external_servers.py", flush=True)


if __name__ == "__main__":
    main()
