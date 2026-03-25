#!/usr/bin/env python3
"""
Request Tracing Middleware

요청별 추적 ID 생성 및 로깅
- X-Trace-ID 헤더 지원
- 응답 헤더에 trace_id 포함
- 요청/응답 로깅
"""

import time
import logging
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from total_llm.utils.logging_config import (
    set_trace_context,
    get_trace_id,
    clear_trace_context,
    generate_trace_id
)

logger = logging.getLogger(__name__)


class TracingMiddleware(BaseHTTPMiddleware):
    """
    요청 추적 미들웨어

    기능:
    1. 요청별 trace_id 생성/전파
    2. 요청/응답 시간 측정
    3. 구조화된 로깅
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract or generate trace_id
        trace_id = request.headers.get("X-Trace-ID") or generate_trace_id()

        # Extract user_id from auth header if available
        user_id = None
        auth_header = request.headers.get("Authorization")
        if auth_header:
            # Simple extraction (improve with JWT decoding if needed)
            user_id = request.headers.get("X-User-ID", "authenticated")

        # Set trace context
        set_trace_context(trace_id, user_id)

        # Log request
        start_time = time.perf_counter()
        logger.info(
            f"→ {request.method} {request.url.path}",
            extra={
                "event": "request_start",
                "method": request.method,
                "path": request.url.path,
                "query": str(request.query_params) if request.query_params else None,
                "client_ip": request.client.host if request.client else None,
            }
        )

        try:
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log response
            log_level = logging.INFO if response.status_code < 400 else logging.WARNING
            logger.log(
                log_level,
                f"← {request.method} {request.url.path} [{response.status_code}] {duration_ms:.1f}ms",
                extra={
                    "event": "request_end",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 2),
                }
            )

            # Add trace_id to response headers
            response.headers["X-Trace-ID"] = trace_id

            return response

        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                f"✗ {request.method} {request.url.path} - Error: {str(e)}",
                extra={
                    "event": "request_error",
                    "method": request.method,
                    "path": request.url.path,
                    "error": str(e),
                    "duration_ms": round(duration_ms, 2),
                }
            )
            raise

        finally:
            clear_trace_context()


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    간단한 요청 로깅 미들웨어 (개발용)

    TracingMiddleware보다 가벼운 버전
    """

    def __init__(self, app, exclude_paths: list = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/health", "/", "/metrics"]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip excluded paths
        if request.url.path in self.exclude_paths:
            return await call_next(request)

        start_time = time.perf_counter()

        response = await call_next(request)

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Only log if duration > 100ms or error
        if duration_ms > 100 or response.status_code >= 400:
            logger.info(
                f"{request.method} {request.url.path} - {response.status_code} ({duration_ms:.0f}ms)"
            )

        return response
