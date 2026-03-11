"""
=============================================================================
Circuit Breaker - 서비스 장애 격리 패턴
=============================================================================

📌 Circuit Breaker란?
    전기 회로의 차단기(Circuit Breaker)에서 이름을 따왔습니다.
    전기 과부하 시 차단기가 내려가듯, 서비스 장애 시 요청을 차단합니다.

💡 왜 필요한가요?
    서비스 A가 다운되면:

    Circuit Breaker 없이:
        요청1 → [30초 타임아웃] → 실패
        요청2 → [30초 타임아웃] → 실패
        요청3 → [30초 타임아웃] → 실패
        → 모든 요청이 30초씩 대기, 전체 시스템 느려짐

    Circuit Breaker 있으면:
        요청1 → [30초 타임아웃] → 실패 (failure_count=1)
        요청2 → [30초 타임아웃] → 실패 (failure_count=2)
        ...
        요청5 → 실패 (failure_count=5) → Circuit OPEN!
        요청6 → [즉시 에러 반환] → 대기 없음
        요청7 → [즉시 에러 반환] → 대기 없음
        (60초 후)
        요청8 → [테스트 요청] → 성공 → Circuit CLOSED

🔄 상태 전이:
    CLOSED (정상)
        ↓ failure_count >= threshold (5번 실패)
    OPEN (차단) ─────────────────────────────┐
        ↓ recovery_timeout 경과 (60초)       │
    HALF_OPEN (테스트)                       │
        ├─ 성공 → CLOSED (정상 복구)         │
        └─ 실패 → OPEN (다시 차단) ──────────┘

📊 설정 값:
    - failure_threshold: 5 (5번 실패하면 OPEN)
    - recovery_timeout: 60초 (60초 후 HALF_OPEN으로 전환)
    - half_open_max_calls: 3 (테스트 요청 최대 3번)
"""

import asyncio
import time
import logging
from enum import Enum
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass, field


logger = logging.getLogger("api-gateway.circuit-breaker")


# =============================================================================
# Circuit Breaker 상태
# =============================================================================

class CircuitState(Enum):
    """
    Circuit Breaker 상태 정의

    CLOSED: 정상 상태, 모든 요청 통과
    OPEN: 차단 상태, 모든 요청 즉시 실패
    HALF_OPEN: 테스트 상태, 일부 요청만 통과시켜 복구 여부 확인
    """
    CLOSED = "closed"       # 정상 - 요청 통과
    OPEN = "open"           # 차단 - 요청 거부
    HALF_OPEN = "half_open" # 테스트 - 일부 요청 허용


# =============================================================================
# Circuit Breaker 예외
# =============================================================================

class CircuitBreakerError(Exception):
    """
    Circuit이 OPEN 상태일 때 발생하는 예외

    이 예외가 발생하면 백엔드 서비스에 요청을 보내지 않고
    즉시 에러를 반환합니다.
    """
    def __init__(self, service_name: str, retry_after: float):
        self.service_name = service_name
        self.retry_after = retry_after  # 몇 초 후 재시도 가능한지
        super().__init__(
            f"Circuit breaker is OPEN for service '{service_name}'. "
            f"Retry after {retry_after:.1f} seconds."
        )


# =============================================================================
# Circuit Breaker 설정
# =============================================================================

@dataclass
class CircuitBreakerConfig:
    """
    Circuit Breaker 설정

    Attributes:
        failure_threshold: OPEN으로 전환되는 실패 횟수 (기본 5)
        recovery_timeout: OPEN → HALF_OPEN 전환 시간 (기본 60초)
        half_open_max_calls: HALF_OPEN 상태에서 허용할 최대 요청 수 (기본 3)
        failure_window: 실패 카운트 초기화 시간 (기본 60초)
    """
    failure_threshold: int = 5          # 5번 실패하면 OPEN
    recovery_timeout: float = 60.0      # 60초 후 HALF_OPEN
    half_open_max_calls: int = 3        # HALF_OPEN에서 3번 테스트
    failure_window: float = 60.0        # 60초 이내 실패만 카운트


# =============================================================================
# Circuit Breaker 상태 저장소
# =============================================================================

@dataclass
class CircuitBreakerState:
    """
    개별 서비스의 Circuit Breaker 상태

    각 서비스(user-service, chat-service 등)마다 별도의 상태를 유지합니다.
    """
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    last_state_change_time: float = field(default_factory=time.time)
    half_open_calls: int = 0
    half_open_successes: int = 0

    def reset(self):
        """상태 초기화 (CLOSED로 복구)"""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.last_state_change_time = time.time()
        self.half_open_calls = 0
        self.half_open_successes = 0


# =============================================================================
# Circuit Breaker 메인 클래스
# =============================================================================

class CircuitBreaker:
    """
    📌 Circuit Breaker 구현

    서비스별로 장애를 감지하고 요청을 차단/허용합니다.

    사용 예시:
        breaker = CircuitBreaker()

        # 요청 전에 확인
        if breaker.can_execute("user-service"):
            try:
                response = await http_client.get(url)
                breaker.record_success("user-service")
            except Exception as e:
                breaker.record_failure("user-service")
                raise
        else:
            raise CircuitBreakerError("user-service", breaker.get_retry_after("user-service"))
    """

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        """
        Args:
            config: Circuit Breaker 설정 (기본값 사용 가능)
        """
        self.config = config or CircuitBreakerConfig()
        self._states: Dict[str, CircuitBreakerState] = {}
        self._lock = asyncio.Lock()

    def _get_state(self, service_name: str) -> CircuitBreakerState:
        """서비스별 상태 조회 (없으면 생성)"""
        if service_name not in self._states:
            self._states[service_name] = CircuitBreakerState()
        return self._states[service_name]

    def can_execute(self, service_name: str) -> bool:
        """
        📌 요청 실행 가능 여부 확인

        Args:
            service_name: 서비스 이름 (예: "user-service")

        Returns:
            True: 요청 가능
            False: 요청 차단 (Circuit OPEN)
        """
        state = self._get_state(service_name)
        current_time = time.time()

        if state.state == CircuitState.CLOSED:
            # 정상 상태 - 항상 허용
            return True

        elif state.state == CircuitState.OPEN:
            # 차단 상태 - recovery_timeout 경과 여부 확인
            elapsed = current_time - state.last_state_change_time

            if elapsed >= self.config.recovery_timeout:
                # 시간 경과 → HALF_OPEN으로 전환
                state.state = CircuitState.HALF_OPEN
                state.last_state_change_time = current_time
                state.half_open_calls = 0
                state.half_open_successes = 0

                logger.info(
                    f"Circuit HALF_OPEN for '{service_name}' "
                    f"(testing recovery after {elapsed:.1f}s)"
                )
                return True
            else:
                # 아직 대기 시간 안 됨 → 차단
                return False

        else:  # HALF_OPEN
            # 테스트 상태 - 제한된 요청만 허용
            if state.half_open_calls < self.config.half_open_max_calls:
                state.half_open_calls += 1
                return True
            else:
                # 테스트 요청 수 초과 → 결과 대기 중
                return False

    def record_success(self, service_name: str) -> None:
        """
        📌 요청 성공 기록

        HALF_OPEN 상태에서 성공하면 CLOSED로 복구합니다.

        Args:
            service_name: 서비스 이름
        """
        state = self._get_state(service_name)

        if state.state == CircuitState.HALF_OPEN:
            state.half_open_successes += 1

            # 테스트 요청이 모두 성공하면 CLOSED로 복구
            if state.half_open_successes >= self.config.half_open_max_calls:
                state.reset()
                logger.info(
                    f"Circuit CLOSED for '{service_name}' "
                    f"(recovered after {self.config.half_open_max_calls} successful calls)"
                )

        elif state.state == CircuitState.CLOSED:
            # 정상 상태에서 성공 → 실패 카운트 감소
            if state.failure_count > 0:
                state.failure_count = max(0, state.failure_count - 1)

    def record_failure(self, service_name: str) -> None:
        """
        📌 요청 실패 기록

        실패 횟수가 threshold에 도달하면 OPEN으로 전환합니다.

        Args:
            service_name: 서비스 이름
        """
        state = self._get_state(service_name)
        current_time = time.time()

        if state.state == CircuitState.HALF_OPEN:
            # 테스트 중 실패 → 다시 OPEN
            state.state = CircuitState.OPEN
            state.last_state_change_time = current_time

            logger.warning(
                f"Circuit OPEN for '{service_name}' "
                f"(failed during HALF_OPEN test)"
            )

        elif state.state == CircuitState.CLOSED:
            # 실패 윈도우 초과 시 카운트 리셋
            if current_time - state.last_failure_time > self.config.failure_window:
                state.failure_count = 0

            state.failure_count += 1
            state.last_failure_time = current_time

            logger.debug(
                f"Failure recorded for '{service_name}' "
                f"(count: {state.failure_count}/{self.config.failure_threshold})"
            )

            # threshold 도달 → OPEN
            if state.failure_count >= self.config.failure_threshold:
                state.state = CircuitState.OPEN
                state.last_state_change_time = current_time

                logger.warning(
                    f"Circuit OPEN for '{service_name}' "
                    f"(threshold reached: {state.failure_count} failures)"
                )

    def get_retry_after(self, service_name: str) -> float:
        """
        📌 재시도 가능 시간 반환

        Circuit이 OPEN 상태일 때, 몇 초 후에 재시도 가능한지 반환합니다.

        Args:
            service_name: 서비스 이름

        Returns:
            남은 대기 시간 (초)
        """
        state = self._get_state(service_name)

        if state.state != CircuitState.OPEN:
            return 0.0

        elapsed = time.time() - state.last_state_change_time
        remaining = self.config.recovery_timeout - elapsed

        return max(0.0, remaining)

    def get_state(self, service_name: str) -> CircuitState:
        """서비스의 현재 상태 조회"""
        return self._get_state(service_name).state

    def get_all_states(self) -> Dict[str, dict]:
        """
        📌 모든 서비스의 상태 조회 (모니터링용)

        Returns:
            {
                "user-service": {
                    "state": "closed",
                    "failure_count": 0,
                    "retry_after": 0.0
                },
                ...
            }
        """
        result = {}

        for service_name, state in self._states.items():
            result[service_name] = {
                "state": state.state.value,
                "failure_count": state.failure_count,
                "retry_after": self.get_retry_after(service_name)
            }

        return result

    def force_open(self, service_name: str) -> None:
        """수동으로 Circuit OPEN (테스트/운영용)"""
        state = self._get_state(service_name)
        state.state = CircuitState.OPEN
        state.last_state_change_time = time.time()
        logger.warning(f"Circuit manually OPENED for '{service_name}'")

    def force_close(self, service_name: str) -> None:
        """수동으로 Circuit CLOSED (테스트/운영용)"""
        state = self._get_state(service_name)
        state.reset()
        logger.info(f"Circuit manually CLOSED for '{service_name}'")


# =============================================================================
# 전역 인스턴스 (싱글톤)
# =============================================================================

_circuit_breaker: Optional[CircuitBreaker] = None


def init_circuit_breaker(config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
    """
    📌 Circuit Breaker 초기화

    애플리케이션 시작 시 호출합니다.

    Args:
        config: 설정 (기본값 사용 가능)

    Returns:
        CircuitBreaker 인스턴스
    """
    global _circuit_breaker
    _circuit_breaker = CircuitBreaker(config)
    logger.info(
        f"Circuit Breaker initialized "
        f"(threshold={_circuit_breaker.config.failure_threshold}, "
        f"recovery_timeout={_circuit_breaker.config.recovery_timeout}s)"
    )
    return _circuit_breaker


def get_circuit_breaker() -> CircuitBreaker:
    """
    📌 Circuit Breaker 인스턴스 반환

    Returns:
        CircuitBreaker 인스턴스

    Raises:
        RuntimeError: 초기화되지 않은 경우
    """
    if _circuit_breaker is None:
        raise RuntimeError(
            "Circuit Breaker not initialized. Call init_circuit_breaker() first."
        )
    return _circuit_breaker
