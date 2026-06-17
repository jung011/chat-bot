"""도구 반환 포맷 표준 (§08 §5.1).

모든 도구는 일관된 dict 를 반환한다. 직접 dict 를 만들지 말고 이 헬퍼를 사용한다.
- 성공: {"success": True, ...데이터}
- 실패/빈 결과: {"success": False, "message": "사람이 읽을 수 있는 사유"}

fail 의 message 는 사용자에게 그대로 전달될 수 있으므로 명확·정중하게 작성한다.
"""
from __future__ import annotations

from typing import Any


def ok(**data: Any) -> dict:
    return {"success": True, **data}


def fail(message: str) -> dict:
    return {"success": False, "message": message}
