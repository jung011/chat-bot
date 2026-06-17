"""DB 스키마 초기화 — scripts/schema.sql 을 기존 Postgres 컨테이너에 적용한다.

실행: python scripts/init_db.py
(idempotent — CREATE ... IF NOT EXISTS)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import psycopg

# 프로젝트 루트를 import path 에 추가
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.core.config import settings  # noqa: E402

SCHEMA = Path(__file__).with_name("schema.sql").read_text(encoding="utf-8")


async def main() -> None:
    async with await psycopg.AsyncConnection.connect(settings.postgres_dsn) as conn:
        await conn.execute(SCHEMA)
        await conn.commit()
    print("schema applied OK")


if __name__ == "__main__":
    asyncio.run(main())
