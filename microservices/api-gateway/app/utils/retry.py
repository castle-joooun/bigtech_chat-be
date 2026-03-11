"""
=============================================================================
Retry with Exponential Backoff - 재시도 로직
=============================================================================

📌 이 파일이 하는 일:
    일시적인 네트워크 오류나 서비스 장애 시 자동으로 재시도합니다.
    Exponential Backoff는 재시도 간격을 점점 늘려서
    서버에 부담을 주지 않으면서 복구 기회를 제공합니다.

💡 Exponential Backoff란?
    재시도할 때마다 대기 시간을 2배씩 늘립니다.

    Linear (선형):
        실패 → 1초 대기 → 실패 → 1초 대기 → 실패 → 1초 대기
        (서버가 과부하 상태면 계속 요청 → 더 나빠짐)

    Exponential (지수):
        실패 → 1초 대기 → 실패 → 2초 대기 → 실패 → 4초 대기
        (서버에 복구 시간을 줌)

🎲 Jitter (무작위 지연)란?
    여러 클라이언트가 동시에 재시도하면 또 과부하가 됩니다.
    무작위 지연을 추가하면 요청이 분산됩니다.

    Jitter 없이:
        Client1: 1초 → 재시도
        Client2: 1초 → 재시도
        Client3: 1초 → 재시도
        (동시 요청 폭주)

    Jitter 있으면:
        Client1: 0.8초 → 재시도
        Client2: 1.2초 → 재시도
        Client3: 0.9초 → 재시도
        (요청 분산)

📊 기본 설정:
    - max_retries: 3 (최대 3번 재시도)
    - base_delay: 1.0초 (첫 재시도 대기)
    - max_delay: 10.0초 (최대 대기 시간)
    - exponential_base: 2 (대기 시간 배수)
"""

import asyncio
import random
import logging
from typing import Callable, Optional, Tuple, Type, Set
from functools import wraps
from dataclasses import dataclass

import httpx


logger = logging.getLogger("api-gateway.retry")


# =============================================================================
# 재시도 설정
# =============================================================================

@dataclass
class RetryConfig:
    """
    재시도 설정

    Attributes:
        max_retries: 최대 재시도 횟수 (기본 3)
        base_delay: 첫 재시도 대기 시간 (기본 1초)
        max_delay: 최대 대기 시간 (기본 10초)
        exponential_base: 대기 시간 배수 (기본 2)
        jitter: 무작위 지연 비율 (기본 0.1 = ±10%)
    """
    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 10.0
    exponential_base: float = 2.0
    jitter: float = 0.1  # ±10% 무작위 지연


# =============================================================================
# 재시도 대상 예외
# =============================================================================

# 이 예외들은 일시적 오류일 가능성이 높아 재시도 대상
RETRYABLE_EXCEPTIONS: Tuple[Type[Exception], ...] = (
    httpx.ConnectError,      # 연결 실패
    httpx.ConnectTimeout,    # 연결 타임아웃
    httpx.ReadTimeout,       # 읽기 타임아웃
    httpx.WriteTimeout,      # 쓰기 타임아웃
    httpx.PoolTimeout,       # 연결 풀 타임아웃
    ConnectionError,         # 일반 연결 오류
    TimeoutError,            # 일반 타임아웃
)

# 재시도 가능한 HTTP 상태 코드
RETRYABLE_STATUS_CODES: Set[int] = {
    408,  # Request Timeout
    429,  # Too Many Requests (Rate Limited)
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
}


# =============================================================================
# 대기 시간 계산
# =============================================================================

def calculate_delay(
    attempt: int,
    config: RetryConfig
) -> float:
    """
    📌 재시도 대기 시간 계산 (Exponential Backoff with Jitter)

    Args:
        attempt: 현재 시도 횟수 (0부터 시작)
        config: 재시도 설정

    Returns:
        대기 시간 (초)

    Example:
        attempt=0: 1.0초 (base_delay)
        attempt=1: 2.0초 (1.0 * 2)
        attempt=2: 4.0초 (1.0 * 2 * 2)
        attempt=3: 8.0초 (1.0 * 2 * 2 * 2)
        (max_delay=10초로 제한)
    """
    # 지수 계산: base_delay * (exponential_base ^ attempt)
    delay = config.base_delay * (config.exponential_base ** attempt)

    # 최대 대기 시간 제한
    delay = min(delay, config.max_delay)

    # Jitter 추가 (±jitter%)
    jitter_range = delay * config.jitter
    delay += random.uniform(-jitter_range, jitter_range)

    return max(0.0, delay)


# =============================================================================
# 재시도 가능 여부 확인
# =============================================================================

def is_retryable_exception(exception: Exception) -> bool:
    """
    📌 재시도 가능한 예외인지 확인

    Args:
        exception: 발생한 예외

    Returns:
        True: 재시도 가능 (일시적 오류)
        False: 재시도 불가 (영구적 오류)
    """
    return isinstance(exception, RETRYABLE_EXCEPTIONS)


def is_retryable_status_code(status_code: int) -> bool:
    """
    📌 재시도 가능한 HTTP 상태 코드인지 확인

    Args:
        status_code: HTTP 상태 코드

    Returns:
        True: 재시도 가능 (서버 오류, 과부하)
        False: 재시도 불가 (클라이언트 오류)
    """
    return status_code in RETRYABLE_STATUS_CODES


# =============================================================================
# 재시도 실행 함수
# =============================================================================

async def retry_async(
    func: Callable,
    *args,
    config: Optional[RetryConfig] = None,
    on_retry: Optional[Callable[[int, Exception, float], None]] = None,
    **kwargs
):
    """
    📌 비동기 함수 재시도 실행

    Args:
        func: 실행할 비동기 함수
        *args: 함수 인자
        config: 재시도 설정 (기본값 사용 가능)
        on_retry: 재시도 시 콜백 (attempt, exception, delay)
        **kwargs: 함수 키워드 인자

    Returns:
        함수 실행 결과

    Raises:
        마지막 시도의 예외

    Example:
        result = await retry_async(
            http_client.get,
            "http://user-service:8005/users",
            config=RetryConfig(max_retries=3)
        )
    """
    config = config or RetryConfig()
    last_exception: Optional[Exception] = None

    for attempt in range(config.max_retries + 1):
        try:
            return await func(*args, **kwargs)

        except Exception as e:
            last_exception = e

            # 재시도 불가능한 예외면 즉시 발생
            if not is_retryable_exception(e):
                raise

            # 마지막 시도였으면 예외 발생
            if attempt >= config.max_retries:
                raise

            # 대기 시간 계산
            delay = calculate_delay(attempt, config)

            # 재시도 로깅
            logger.warning(
                f"Retry attempt {attempt + 1}/{config.max_retries} "
                f"after {delay:.2f}s due to: {type(e).__name__}: {e}"
            )

            # 콜백 호출
            if on_retry:
                on_retry(attempt + 1, e, delay)

            # 대기
            await asyncio.sleep(delay)

    # 여기에 도달하면 안 되지만, 안전을 위해
    if last_exception:
        raise last_exception


# =============================================================================
# 데코레이터 버전
# =============================================================================

def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential_base: float = 2.0,
    jitter: float = 0.1
):
    """
    📌 재시도 데코레이터

    함수에 자동 재시도 기능을 추가합니다.

    Args:
        max_retries: 최대 재시도 횟수
        base_delay: 첫 재시도 대기 시간
        max_delay: 최대 대기 시간
        exponential_base: 대기 시간 배수
        jitter: 무작위 지연 비율

    Example:
        @with_retry(max_retries=3, base_delay=1.0)
        async def call_external_api():
            return await http_client.get(url)
    """
    config = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter
    )

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(func, *args, config=config, **kwargs)
        return wrapper

    return decorator
