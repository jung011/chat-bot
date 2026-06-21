"""도구 반환 포맷 표준."""
from __future__ import annotations

from typing import Any


def ok(**data: Any) -> dict:
    return {"success": True, **data}


def fail(message: str) -> dict:
    return {"success": False, "message": message}
