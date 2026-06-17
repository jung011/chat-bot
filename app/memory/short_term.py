"""단기 대화 메모리 (§04 §5, §06 §8).

Redis key `chat:{company_id}:{session_id}` 에 최근 대화를 리스트로 보관한다.
멀티턴 컨텍스트를 빠르게 조회하기 위함이며, 최근 N턴만 유지(절단)한다.
(장기 메모리/요약은 파일럿 범위 밖 — §05.)
"""
from __future__ import annotations

import json

from app.db import redis_client

_MAX_TURNS = 20          # 최근 N개 메시지 유지(절단, §06 §8)
_TTL_SECONDS = 6 * 3600  # 수 시간(§04 §5)


def _key(company_id: str, session_id: str) -> str:
    return f"chat:{company_id}:{session_id}"


async def append(company_id: str, session_id: str, role: str, content: str) -> None:
    r = redis_client.get_client()
    key = _key(company_id, session_id)
    await r.rpush(key, json.dumps({"role": role, "content": content}))
    await r.ltrim(key, -_MAX_TURNS, -1)
    await r.expire(key, _TTL_SECONDS)


async def history(company_id: str, session_id: str, limit: int = _MAX_TURNS) -> list[dict]:
    """[{role, content}] 시간순. 없으면 빈 리스트."""
    r = redis_client.get_client()
    raw = await r.lrange(_key(company_id, session_id), -limit, -1)
    return [json.loads(x) for x in raw]


def history_text(turns: list[dict]) -> str:
    """프롬프트 주입용 히스토리 문자열(§06 {history})."""
    label = {"user": "사용자", "assistant": "상담원"}
    return "\n".join(f"{label.get(t['role'], t['role'])}: {t['content']}" for t in turns)
