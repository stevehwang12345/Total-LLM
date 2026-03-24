#!/usr/bin/env python3
"""
Structured Logging Configuration

JSON 형식의 구조화된 로깅 설정
- ELK 스택 연동 준비
- 요청 추적 (trace_id)
- 환경별 설정 (development, production)
"""

import logging
import logging.handlers
import json
import sys
import os
from datetime import datetime
from typing import Optional, Dict, Any
from contextvars import ContextVar
import uuid

# Context variables for request tracing
trace_id_var: ContextVar[str] = ContextVar('trace_id', default='')
user_id_var: ContextVar[str] = ContextVar('user_id', default='anonymous')


class JSONFormatter(logging.Formatter):
    """
    JSON 형식 로그 포매터

    출력 형식:
    {
        "timestamp": "2026-02-05T10:30:00.000Z",
        "level": "INFO",
        "logger": "main",
        "message": "Server started",
        "trace_id": "abc123",
        "user_id": "user1",
        "extra": {...}
    }
    """

    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add trace context
        trace_id = trace_id_var.get()
        if trace_id:
            log_data["trace_id"] = trace_id

        user_id = user_id_var.get()
        if user_id and user_id != 'anonymous':
            log_data["user_id"] = user_id

        # Add exception info
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if self.include_extra:
            extra_fields = {}
            for key, value in record.__dict__.items():
                if key not in (
                    'name', 'msg', 'args', 'created', 'filename', 'funcName',
                    'levelname', 'levelno', 'lineno', 'module', 'msecs',
                    'pathname', 'process', 'processName', 'relativeCreated',
                    'stack_info', 'exc_info', 'exc_text', 'thread', 'threadName',
                    'message', 'taskName'
                ):
                    try:
                        json.dumps(value)  # Check if serializable
                        extra_fields[key] = value
                    except (TypeError, ValueError):
                        extra_fields[key] = str(value)

            if extra_fields:
                log_data["extra"] = extra_fields

        return json.dumps(log_data, ensure_ascii=False)


class ColoredConsoleFormatter(logging.Formatter):
    """
    개발 환경용 컬러 콘솔 포매터
    """

    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, self.RESET)

        # Add trace_id if available
        trace_id = trace_id_var.get()
        trace_str = f"[{trace_id[:8]}] " if trace_id else ""

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return (
            f"{color}{timestamp} [{record.levelname:^8}]{self.RESET} "
            f"{trace_str}{record.name}: {record.getMessage()}"
        )


def setup_logging(
    level: str = "INFO",
    json_format: bool = False,
    log_file: Optional[str] = None,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> None:
    """
    로깅 설정 초기화

    Args:
        level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_format: JSON 형식 사용 여부 (프로덕션에서 True)
        log_file: 로그 파일 경로 (선택)
        max_bytes: 로그 파일 최대 크기
        backup_count: 백업 파일 수
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))

    if json_format:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(ColoredConsoleFormatter())

    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(getattr(logging, level.upper()))
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)

    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logging_config_from_env() -> Dict[str, Any]:
    """
    환경변수에서 로깅 설정 읽기

    환경변수:
        - LOG_LEVEL: 로그 레벨 (default: INFO)
        - LOG_FORMAT: json 또는 console (default: console)
        - LOG_FILE: 로그 파일 경로 (optional)
        - ENVIRONMENT: development 또는 production
    """
    environment = os.getenv("ENVIRONMENT", "development")

    return {
        "level": os.getenv("LOG_LEVEL", "INFO"),
        "json_format": os.getenv("LOG_FORMAT", "json" if environment == "production" else "console") == "json",
        "log_file": os.getenv("LOG_FILE"),
    }


# ============================================
# Request Tracing Utilities
# ============================================

def generate_trace_id() -> str:
    """새 trace_id 생성"""
    return str(uuid.uuid4())


def set_trace_context(trace_id: Optional[str] = None, user_id: Optional[str] = None) -> str:
    """
    요청 추적 컨텍스트 설정

    Args:
        trace_id: 추적 ID (없으면 자동 생성)
        user_id: 사용자 ID

    Returns:
        설정된 trace_id
    """
    if trace_id is None:
        trace_id = generate_trace_id()

    trace_id_var.set(trace_id)

    if user_id:
        user_id_var.set(user_id)

    return trace_id


def get_trace_id() -> str:
    """현재 trace_id 반환"""
    return trace_id_var.get()


def clear_trace_context() -> None:
    """추적 컨텍스트 초기화"""
    trace_id_var.set('')
    user_id_var.set('anonymous')


# ============================================
# Logging with Extra Fields
# ============================================

class StructuredLogger:
    """
    구조화된 로깅을 위한 래퍼 클래스

    사용법:
        logger = StructuredLogger(__name__)
        logger.info("User logged in", user_id="user123", ip="192.168.1.1")
    """

    def __init__(self, name: str):
        self._logger = logging.getLogger(name)

    def _log(self, level: int, msg: str, **kwargs) -> None:
        self._logger.log(level, msg, extra=kwargs)

    def debug(self, msg: str, **kwargs) -> None:
        self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: str, **kwargs) -> None:
        self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: str, **kwargs) -> None:
        self._log(logging.WARNING, msg, **kwargs)

    def error(self, msg: str, **kwargs) -> None:
        self._log(logging.ERROR, msg, **kwargs)

    def critical(self, msg: str, **kwargs) -> None:
        self._log(logging.CRITICAL, msg, **kwargs)

    def exception(self, msg: str, **kwargs) -> None:
        self._logger.exception(msg, extra=kwargs)


def get_logger(name: str) -> StructuredLogger:
    """구조화된 로거 반환"""
    return StructuredLogger(name)
