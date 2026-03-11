"""
구조화된 로깅 시스템 (Structured Logging System)

================================================================================
아키텍처 개요 (Architecture Overview)
================================================================================
JSON 형식의 구조화된 로그를 제공하여 로그 분석과 모니터링을 용이하게 합니다.
ELK Stack (Elasticsearch, Logstash, Kibana)이나 Datadog 등의 로그 분석 도구와
쉽게 통합할 수 있도록 설계되었습니다.

로그 처리 흐름:
    로그 이벤트 발생 → StructuredFormatter → JSON 변환 → 핸들러 출력
                                    ↓
                    컨텍스트 정보 (request_id, user_id) 자동 추가

로그 출력 대상:
    ├── 콘솔 (stdout): 개발 환경은 일반 포맷, 프로덕션은 JSON
    ├── app.log: 모든 로그 (INFO 이상)
    └── error.log: 에러 로그만 (ERROR 이상)

================================================================================
디자인 패턴 (Design Patterns)
================================================================================
1. Singleton Pattern (싱글톤 패턴)
   - setup_logging()으로 한 번만 초기화
   - get_logger()로 로거 인스턴스 획득

2. Decorator Pattern (데코레이터 패턴)
   - StructuredFormatter가 LogRecord를 JSON으로 변환
   - 기존 로깅 시스템을 확장

3. Context Object Pattern (컨텍스트 객체 패턴)
   - contextvars를 사용하여 요청별 추적 정보 저장
   - 비동기 환경에서도 안전하게 컨텍스트 전파

================================================================================
SOLID 원칙 적용 (SOLID Principles)
================================================================================
- SRP (단일 책임): 각 로그 함수는 하나의 이벤트 타입만 기록
- OCP (개방-폐쇄): 새로운 로그 타입 추가 시 기존 코드 수정 없음
- DIP (의존성 역전): Python 표준 logging 모듈에 의존

================================================================================
로그 수준 가이드 (Log Level Guide)
================================================================================
- DEBUG: 디버깅용 상세 정보 (개발 환경에서만 활성화)
- INFO: 정상 작업 흐름 기록 (API 호출, DB 작업 등)
- WARNING: 잠재적 문제 상황 (보안 이벤트, 폴백 동작)
- ERROR: 오류 상황 (예외 발생, 외부 서비스 실패)
- CRITICAL: 심각한 오류 (시스템 중단 수준)

================================================================================
사용 예시 (Usage Examples)
================================================================================
>>> from legacy.app.core.logging import get_logger, log_api_call
>>>
>>> logger = get_logger(__name__)
>>> logger.info("사용자 생성 완료", extra={"user_id": 123})
>>>
>>> log_api_call(logger, "POST", "/auth/login", 200, 45.2, user_id=123)
"""

import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, Optional
from contextvars import ContextVar
from pathlib import Path

from legacy.app.core.config import settings

# =============================================================================
# 컨텍스트 변수 (Context Variables)
# =============================================================================
# asyncio 환경에서 요청별 추적 정보를 안전하게 저장합니다.
# 각 요청은 독립적인 컨텍스트를 가지며, 로그에 자동으로 포함됩니다.
# =============================================================================
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[int]] = ContextVar('user_id', default=None)


class StructuredFormatter(logging.Formatter):
    """
    구조화된 JSON 로그 포매터

    Python의 LogRecord를 JSON 형식으로 변환합니다.
    모든 로그에 타임스탬프, 레벨, 위치 정보를 포함하며,
    컨텍스트 변수(request_id, user_id)가 있으면 자동으로 추가합니다.

    출력 예시:
        {
            "timestamp": "2024-01-15T10:30:00.000Z",
            "level": "INFO",
            "logger": "app.api.auth",
            "message": "사용자 로그인 성공",
            "module": "auth",
            "function": "login",
            "line": 45,
            "request_id": "req-123",
            "user_id": 456,
            "extra": {"email": "user@example.com"}
        }
    """

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
    """
    로깅 시스템 초기화

    애플리케이션 시작 시 한 번 호출하여 로깅을 설정합니다.
    - 로그 디렉토리 생성
    - 콘솔 핸들러 설정 (환경에 따라 포맷 변경)
    - 파일 핸들러 설정 (app.log, error.log)
    - 외부 라이브러리 로그 레벨 조정

    Note:
        main.py의 lifespan 함수에서 호출됩니다.
    """

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
    """
    구조화된 로거 인스턴스 반환

    Args:
        name: 로거 이름 (일반적으로 __name__ 사용)

    Returns:
        logging.Logger: 구성된 로거 인스턴스

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("작업 완료", extra={"duration": 150})
    """
    return logging.getLogger(name)


def set_request_context(request_id: str, user_id: Optional[int] = None):
    """
    요청 컨텍스트 설정

    미들웨어에서 호출하여 요청별 추적 정보를 설정합니다.
    설정된 정보는 해당 요청의 모든 로그에 자동으로 포함됩니다.

    Args:
        request_id: 요청 고유 ID (UUID 권장)
        user_id: 인증된 사용자 ID (선택사항)

    Example:
        >>> set_request_context("req-abc-123", user_id=456)
    """
    request_id_var.set(request_id)
    if user_id:
        user_id_var.set(user_id)


def clear_request_context():
    """
    요청 컨텍스트 초기화

    요청 처리 완료 후 미들웨어에서 호출하여 컨텍스트를 정리합니다.
    """
    request_id_var.set(None)
    user_id_var.set(None)


# =============================================================================
# 도메인별 로그 함수들 (Domain-Specific Log Functions)
# =============================================================================
# 각 도메인에 특화된 로그 함수를 제공하여 일관된 로그 형식을 보장합니다.
# 모든 함수는 event_type 필드를 포함하여 로그 분류를 용이하게 합니다.
# =============================================================================

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