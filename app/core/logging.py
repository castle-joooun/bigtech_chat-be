"""
구조화된 로깅 시스템

JSON 형식의 구조화된 로그를 제공하여 로그 분석과 모니터링을 용이하게 합니다.
"""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from contextvars import ContextVar
from pathlib import Path

from app.core.config import settings

# 컨텍스트 변수로 요청별 추적 정보 저장
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[int]] = ContextVar('user_id', default=None)


class StructuredFormatter(logging.Formatter):
    """구조화된 JSON 로그 포매터"""

    def format(self, record: logging.LogRecord) -> str:
        # 기본 로그 정보
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # 컨텍스트 정보 추가
        request_id = request_id_var.get()
        if request_id:
            log_data["request_id"] = request_id

        user_id = user_id_var.get()
        if user_id:
            log_data["user_id"] = user_id

        # 예외 정보 추가
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info)
            }

        # 추가 데이터 (extra 필드)
        extra_data = {}
        for key, value in record.__dict__.items():
            if key not in [
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                'thread', 'threadName', 'processName', 'process', 'getMessage'
            ] and not key.startswith('_'):
                extra_data[key] = value

        if extra_data:
            log_data["extra"] = extra_data

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging():
    """로깅 시스템 초기화"""

    # 로그 디렉토리 생성
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # 기존 핸들러 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # 콘솔 핸들러
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)

    if settings.debug:
        # 개발 환경: 사람이 읽기 쉬운 형식
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        # 프로덕션 환경: 구조화된 JSON 형식
        console_formatter = StructuredFormatter()

    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # 파일 핸들러 (항상 구조화된 형식)
    file_handler = logging.FileHandler(log_dir / "app.log", encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(file_handler)

    # 에러 전용 파일 핸들러
    error_handler = logging.FileHandler(log_dir / "error.log", encoding='utf-8')
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(error_handler)

    # 외부 라이브러리 로그 레벨 조정
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """구조화된 로거 인스턴스 반환"""
    return logging.getLogger(name)


def set_request_context(request_id: str, user_id: Optional[int] = None):
    """요청 컨텍스트 설정"""
    request_id_var.set(request_id)
    if user_id:
        user_id_var.set(user_id)


def clear_request_context():
    """요청 컨텍스트 초기화"""
    request_id_var.set(None)
    user_id_var.set(None)


def log_api_call(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    user_id: Optional[int] = None,
    **extra
):
    """API 호출 로그"""
    logger.info(
        f"{method} {path} - {status_code}",
        extra={
            "event_type": "api_call",
            "method": method,
            "path": path,
            "status_code": status_code,
            "duration_ms": duration_ms,
            "user_id": user_id,
            **extra
        }
    )


def log_database_operation(
    logger: logging.Logger,
    operation: str,
    table: str,
    duration_ms: Optional[float] = None,
    affected_rows: Optional[int] = None,
    **extra
):
    """데이터베이스 작업 로그"""
    logger.info(
        f"DB {operation} on {table}",
        extra={
            "event_type": "database_operation",
            "operation": operation,
            "table": table,
            "duration_ms": duration_ms,
            "affected_rows": affected_rows,
            **extra
        }
    )


def log_authentication_event(
    logger: logging.Logger,
    event: str,
    user_id: Optional[int] = None,
    email: Optional[str] = None,
    success: bool = True,
    **extra
):
    """인증 이벤트 로그"""
    logger.info(
        f"Auth {event} - {'Success' if success else 'Failed'}",
        extra={
            "event_type": "authentication",
            "event": event,
            "user_id": user_id,
            "email": email,
            "success": success,
            **extra
        }
    )


def log_websocket_event(
    logger: logging.Logger,
    event: str,
    user_id: int,
    room_id: str,
    **extra
):
    """WebSocket 이벤트 로그"""
    logger.info(
        f"WebSocket {event} - User {user_id} in Room {room_id}",
        extra={
            "event_type": "websocket",
            "event": event,
            "user_id": user_id,
            "room_id": room_id,
            **extra
        }
    )


def log_file_operation(
    logger: logging.Logger,
    operation: str,
    file_path: str,
    user_id: int,
    file_size: Optional[int] = None,
    **extra
):
    """파일 작업 로그"""
    logger.info(
        f"File {operation} - {file_path}",
        extra={
            "event_type": "file_operation",
            "operation": operation,
            "file_path": file_path,
            "user_id": user_id,
            "file_size": file_size,
            **extra
        }
    )


def log_security_event(
    logger: logging.Logger,
    event: str,
    severity: str = "medium",
    user_id: Optional[int] = None,
    ip_address: Optional[str] = None,
    **extra
):
    """보안 이벤트 로그"""
    logger.warning(
        f"Security {event} - Severity: {severity}",
        extra={
            "event_type": "security",
            "event": event,
            "severity": severity,
            "user_id": user_id,
            "ip_address": ip_address,
            **extra
        }
    )


def log_performance_metric(
    logger: logging.Logger,
    metric_name: str,
    value: float,
    unit: str = "ms",
    **extra
):
    """성능 메트릭 로그"""
    logger.info(
        f"Performance {metric_name}: {value}{unit}",
        extra={
            "event_type": "performance_metric",
            "metric_name": metric_name,
            "value": value,
            "unit": unit,
            **extra
        }
    )