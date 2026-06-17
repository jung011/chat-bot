"""커스텀 예외 + 핸들러 (§03 §1.3 공통 에러 형식).

에러 응답 형식:
    {"error": {"code", "message", "details"}, "request_id"}
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """애플리케이션 표준 예외. code/status/message 를 갖는다(§03 §1.5)."""

    code: str = "INTERNAL_ERROR"
    status_code: int = 500

    def __init__(self, message: str, *, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class InvalidRequest(AppError):
    code = "INVALID_REQUEST"
    status_code = 400


class Unauthorized(AppError):
    code = "UNAUTHORIZED"
    status_code = 401


class TenantForbidden(AppError):
    code = "TENANT_FORBIDDEN"
    status_code = 403


class SessionNotFound(AppError):
    code = "SESSION_NOT_FOUND"
    status_code = 404


class RateLimited(AppError):
    code = "RATE_LIMITED"
    status_code = 429


class UpstreamUnavailable(AppError):
    code = "UPSTREAM_UNAVAILABLE"
    status_code = 503


class LLMTimeout(AppError):
    code = "LLM_TIMEOUT"
    status_code = 504


def _request_id(request: Request) -> str | None:
    return request.headers.get("X-Request-Id")


def _envelope(code: str, message: str, details: dict, request_id: str | None) -> dict:
    body: dict = {"error": {"code": code, "message": message, "details": details}}
    if request_id:
        body["request_id"] = request_id
    return body


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(exc.code, exc.message, exc.details, _request_id(request)),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=_envelope(
                "INVALID_REQUEST",
                "요청 형식이 올바르지 않습니다.",
                {"errors": exc.errors()},
                _request_id(request),
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(request: Request, exc: StarletteHTTPException):
        code = {401: "UNAUTHORIZED", 403: "TENANT_FORBIDDEN", 404: "NOT_FOUND"}.get(
            exc.status_code, "HTTP_ERROR"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code, str(exc.detail), {}, _request_id(request)),
        )
