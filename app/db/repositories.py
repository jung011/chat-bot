"""레포지토리 계층 (§04 §4) — Postgres 메타데이터 CRUD.

모든 조회/조작에 company_id 필터를 강제한다(§04 §2 테넌트 격리).
ID 는 추측 어려운 난수(secrets.token_hex)로 발급한다(§03 §5 session_id 난수성).
"""
from __future__ import annotations

import json
import secrets
from typing import Any

from psycopg.rows import dict_row

from app.db import postgres


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(12)}"


async def _conn():
    pool = await postgres.init_pool()
    return pool.connection()


# ── 세션 ──────────────────────────────────────────────────────────────
async def create_session(company_id: str, title: str | None = None) -> dict:
    sid = new_id("sess")
    async with await _conn() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "INSERT INTO sessions (session_id, company_id, title) "
                "VALUES (%s, %s, %s) RETURNING session_id, created_at",
                (sid, company_id, title),
            )
            return await cur.fetchone()


async def get_session(session_id: str, company_id: str) -> dict | None:
    async with await _conn() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT session_id, company_id, title, created_at, updated_at "
                "FROM sessions WHERE session_id=%s AND company_id=%s",
                (session_id, company_id),
            )
            return await cur.fetchone()


async def list_sessions(company_id: str, limit: int = 20) -> list[dict]:
    async with await _conn() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT session_id, title, updated_at FROM sessions "
                "WHERE company_id=%s ORDER BY updated_at DESC LIMIT %s",
                (company_id, limit),
            )
            return await cur.fetchall()


async def delete_session(session_id: str, company_id: str) -> bool:
    async with await _conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "DELETE FROM sessions WHERE session_id=%s AND company_id=%s",
                (session_id, company_id),
            )
            return cur.rowcount > 0


async def touch_session(session_id: str) -> None:
    async with await _conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "UPDATE sessions SET updated_at=now() WHERE session_id=%s", (session_id,)
            )


# ── 메시지 ────────────────────────────────────────────────────────────
async def add_message(
    *,
    session_id: str,
    company_id: str,
    role: str,
    content: str,
    route: str | None = None,
    sources: list | None = None,
    usage: dict | None = None,
    message_id: str | None = None,
) -> str:
    mid = message_id or new_id("msg")
    async with await _conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO messages "
                "(message_id, session_id, company_id, role, content, route, sources, usage) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    mid,
                    session_id,
                    company_id,
                    role,
                    content,
                    route,
                    json.dumps(sources) if sources is not None else None,
                    json.dumps(usage) if usage is not None else None,
                ),
            )
    return mid


async def list_messages(session_id: str, company_id: str, limit: int = 50) -> list[dict]:
    async with await _conn() as conn:
        async with conn.cursor(row_factory=dict_row) as cur:
            await cur.execute(
                "SELECT message_id, role, content, route, created_at FROM messages "
                "WHERE session_id=%s AND company_id=%s ORDER BY created_at LIMIT %s",
                (session_id, company_id, limit),
            )
            return await cur.fetchall()


# ── 피드백 ────────────────────────────────────────────────────────────
async def add_feedback(
    *, message_id: str, company_id: str, rating: str, reason: str | None
) -> None:
    async with await _conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO message_feedback (message_id, company_id, rating, reason) "
                "VALUES (%s,%s,%s,%s)",
                (message_id, company_id, rating, reason),
            )


# ── 질문 로그 (자동완성 log 소스 / 미응답 분석, §06 §10.4) ──────────────
async def log_query(
    *, company_id: str, raw_query: str, route: str | None, matched: bool
) -> None:
    async with await _conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO query_logs (company_id, raw_query, route, matched) "
                "VALUES (%s,%s,%s,%s)",
                (company_id, raw_query, route, matched),
            )


# ── 인덱싱 작업 ────────────────────────────────────────────────────────
async def create_index_job(*, company_id: str, type_: str, scope: str) -> str:
    jid = new_id("job")
    async with await _conn() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO index_jobs (job_id, company_id, type, scope, status) "
                "VALUES (%s,%s,%s,%s,'queued')",
                (jid, company_id, type_, scope),
            )
    return jid
