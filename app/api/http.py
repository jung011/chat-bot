"""HTTP 응답 헬퍼 (§03 §1.3 공통 응답 형식)."""
from __future__ import annotations

from typing import Any

from fastapi import Request


def envelope(data: Any, request: Request | None = None) -> dict:
    body: dict = {"data": data}
    if request is not None:
        rid = request.headers.get("X-Request-Id")
        if rid:
            body["request_id"] = rid
    return body
