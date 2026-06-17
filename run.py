"""로컬 개발 서버 런처 (Windows 안전).

Windows의 기본 asyncio 루프(ProactorEventLoop)는 psycopg async 모드를
지원하지 않는다. uvicorn은 자체 루프를 만든 뒤 앱을 import하므로,
정책은 반드시 uvicorn이 루프를 만들기 *전*에 이 메인 프로세스에서 세팅돼야 한다.

실행:
    python run.py
(또는 `uvicorn app.main:app` 대신 이 스크립트를 사용한다.)
"""
from __future__ import annotations

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
    )
