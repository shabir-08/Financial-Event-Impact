"""Structured application errors and FastAPI handlers."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

log = logging.getLogger(__name__)


class AppError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "details": self.details}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConfigurationError(AppError):
    """Missing credentials or invalid settings for an integration."""

    status_code = 503
    code = "configuration_error"


class ProviderError(AppError):
    """An external provider (news, market data, LLM) failed."""

    status_code = 502
    code = "provider_error"

    def __init__(self, message: str, *, provider: str, retryable: bool = False, **kw: Any) -> None:
        super().__init__(message, details={"provider": provider, "retryable": retryable, **kw})
        self.provider = provider
        self.retryable = retryable


class RateLimitedError(ProviderError):
    code = "rate_limited"
    status_code = 429


class LLMOutputError(AppError):
    """The LLM produced output that failed schema or evidence validation."""

    status_code = 502
    code = "llm_output_invalid"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.to_dict()})

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed",
                    "details": {"errors": _jsonable_errors(exc.errors())},
                }
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def _db_error(_: Request, exc: SQLAlchemyError) -> JSONResponse:
        log.exception("Database error")
        return JSONResponse(
            status_code=503,
            content={"error": {"code": "database_error", "message": "Database operation failed", "details": {}}},
        )


def _jsonable_errors(errors: Any) -> list[dict[str, Any]]:
    out = []
    for e in errors:
        out.append({"loc": list(e.get("loc", [])), "msg": str(e.get("msg")), "type": e.get("type")})
    return out
