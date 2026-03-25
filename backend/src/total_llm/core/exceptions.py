from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppException(Exception):
    def __init__(
        self,
        status_code: int = 500,
        detail: str = "Internal error",
        error_code: str = "INTERNAL_ERROR",
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.detail = detail
        self.error_code = error_code
        self.metadata = metadata or {}
        super().__init__(detail)


class NotFoundError(AppException):
    def __init__(self, detail: str = "Resource not found", resource: str = "") -> None:
        metadata: dict[str, Any] = {"resource": resource} if resource else {}
        super().__init__(404, detail, "NOT_FOUND", metadata)


class ValidationError(AppException):
    def __init__(self, detail: str = "Validation failed", metadata: dict[str, Any] | None = None) -> None:
        super().__init__(422, detail, "VALIDATION_ERROR", metadata)


class ExternalServiceError(AppException):
    def __init__(self, service: str, detail: str = "External service unavailable") -> None:
        super().__init__(503, f"{service}: {detail}", "EXTERNAL_SERVICE_ERROR", {"service": service})


class RAGError(AppException):
    def __init__(self, detail: str = "RAG pipeline error") -> None:
        super().__init__(500, detail, "RAG_ERROR")


class VLMError(AppException):
    def __init__(self, detail: str = "VLM analysis error") -> None:
        super().__init__(500, detail, "VLM_ERROR")


class DeviceControlError(AppException):
    def __init__(self, device_id: str = "", detail: str = "Device control error") -> None:
        metadata: dict[str, Any] = {"device_id": device_id} if device_id else {}
        super().__init__(500, detail, "DEVICE_CONTROL_ERROR", metadata)


class AuthenticationError(AppException):
    def __init__(self, detail: str = "Authentication required") -> None:
        super().__init__(401, detail, "AUTHENTICATION_ERROR")


class AuthorizationError(AppException):
    def __init__(self, detail: str = "Permission denied") -> None:
        super().__init__(403, detail, "AUTHORIZATION_ERROR")


class RateLimitError(AppException):
    def __init__(self, detail: str = "Rate limit exceeded") -> None:
        super().__init__(429, detail, "RATE_LIMIT_ERROR")


def _error_payload(code: str, message: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if metadata:
        payload["error"]["metadata"] = metadata
    return payload


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppException)
    async def app_exception_handler(_: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload(exc.error_code, exc.detail, exc.metadata),
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=_error_payload(
                "REQUEST_VALIDATION_ERROR",
                "Request validation failed",
                {"errors": exc.errors()},
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_payload("HTTP_ERROR", str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, __: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=_error_payload("INTERNAL_SERVER_ERROR", "Internal server error"),
        )
