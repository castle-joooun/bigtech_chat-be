"""
=============================================================================
Reverse Proxy Router - 요청 전달 라우터
=============================================================================

📌 이 파일이 하는 일:
    클라이언트의 요청을 받아서 적절한 백엔드 서비스로 전달합니다.
    마치 우체부가 편지를 올바른 집으로 배달하는 것과 같습니다.

🔄 프록시 흐름:
    1. 클라이언트가 /api/users/1 요청
    2. 이 라우터가 요청을 받음
    3. "users" → user-service로 가야 함을 확인
    4. user-service:8005/api/users/1 로 요청 전달
    5. user-service의 응답을 클라이언트에게 반환

📍 라우팅 규칙 (registry.py에서 정의):
    /api/auth/*      → user-service:8005
    /api/profile/*   → user-service:8005
    /api/users/*     → user-service:8005
    /api/friends/*   → friend-service:8003
    /api/chat-rooms/* → chat-service:8002
    /api/messages/*  → chat-service:8002

💡 왜 프록시가 필요한가요?
    1. 클라이언트는 하나의 주소만 알면 됨 (Gateway 주소)
    2. 백엔드 서비스 주소가 바뀌어도 클라이언트는 수정 불필요
    3. 보안: 백엔드 서비스를 외부에 직접 노출하지 않음

🛡️ 복원력 패턴:
    - Circuit Breaker: 서비스 장애 시 빠른 실패 (연쇄 장애 방지)
    - Retry: 일시적 오류 시 자동 재시도 (Exponential Backoff)
"""

import logging
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import Response, StreamingResponse
import httpx

from ..registry import get_registry
from ..utils.http_client import get_http_client
from ..utils.circuit_breaker import get_circuit_breaker, CircuitBreakerError
from ..utils.retry import (
    RetryConfig,
    retry_async,
    is_retryable_exception,
    is_retryable_status_code,
)


# 로거 설정
logger = logging.getLogger("api-gateway.proxy")

# FastAPI 라우터 인스턴스
router = APIRouter()


# =============================================================================
# 헤더 설정
# =============================================================================

# 백엔드 서비스로 전달할 헤더 목록
# 이 헤더들은 클라이언트 → Gateway → 백엔드 서비스로 그대로 전달됩니다
FORWARDED_HEADERS = [
    "authorization",    # 인증 토큰 (Bearer xxx)
    "content-type",     # 요청 본문 형식 (application/json 등)
    "accept",           # 클라이언트가 원하는 응답 형식
    "accept-language",  # 선호 언어
    "user-agent",       # 클라이언트 정보 (브라우저, 앱 등)
    "x-request-id",     # 요청 추적 ID
    "x-forwarded-for",  # 원본 클라이언트 IP (프록시 경유 시)
    "x-real-ip",        # 실제 클라이언트 IP
]

# 응답에서 제외할 헤더
# 이 헤더들은 Gateway에서 다시 설정하므로 백엔드 응답에서 제외합니다
EXCLUDED_RESPONSE_HEADERS = [
    "transfer-encoding",  # 전송 인코딩 (chunked 등)
    "content-encoding",   # 압축 방식 (gzip 등)
    "content-length",     # 본문 길이 (Gateway에서 재계산)
]


# =============================================================================
# 메인 프록시 엔드포인트
# =============================================================================
@router.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
)
async def proxy_request(request: Request, path: str) -> Response:
    """
    📌 모든 /api/* 요청을 백엔드 서비스로 프록시

    이 함수는 Gateway의 핵심입니다. 모든 API 요청이 여기를 통과합니다.

    Args:
        request: 원본 HTTP 요청 객체
        path: /api/ 이후의 경로
              예: /api/users/1 → path = "users/1"

    Returns:
        Response: 백엔드 서비스의 응답을 그대로 반환

    Raises:
        HTTPException 404: 해당 경로를 처리할 서비스가 없는 경우
        HTTPException 502: 백엔드 서비스 연결 실패

    Example:
        GET /api/users/1
        → user-service:8005/api/users/1 로 전달
        → user-service 응답을 클라이언트에게 반환
    """

    # =========================================================================
    # Step 1: 전체 경로 구성
    # =========================================================================
    full_path = f"/api/{path}"
    # 예: path="users/1" → full_path="/api/users/1"

    # =========================================================================
    # Step 2: 대상 서비스 결정
    # =========================================================================
    # ServiceRegistry에서 경로에 맞는 서비스를 찾습니다
    registry = get_registry()
    service = registry.resolve_route(full_path)

    if not service:
        # 매칭되는 서비스가 없으면 404 에러
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No service found for path: {full_path}"
        )

    # =========================================================================
    # Step 3: 대상 URL 구성
    # =========================================================================
    # 서비스 URL + 경로 + 쿼리 파라미터
    target_url = f"{service.url}{full_path}"

    # 쿼리 파라미터가 있으면 추가
    # 예: ?page=1&limit=10
    if request.query_params:
        target_url = f"{target_url}?{request.query_params}"

    # 예: http://user-service:8005/api/users/1?page=1

    # =========================================================================
    # Step 4: 요청 헤더 준비
    # =========================================================================
    headers = _prepare_headers(request)

    # Request ID 전달 (요청 추적용)
    # 미들웨어에서 생성된 ID가 있으면 전달
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        headers["X-Request-ID"] = request_id

    # 클라이언트 IP 전달
    # 백엔드 서비스에서 원본 클라이언트 IP를 알 수 있게 함
    if request.client:
        headers["X-Forwarded-For"] = request.client.host
        headers["X-Real-IP"] = request.client.host

    # =========================================================================
    # Step 5: 인증 정보 전달 (Gateway에서 JWT 검증 완료된 경우)
    # =========================================================================
    # Gateway에서 JWT를 검증했다면, 사용자 정보를 헤더로 전달
    # 백엔드 서비스는 이 헤더를 신뢰하고 다시 검증하지 않아도 됨
    user = getattr(request.state, "user", None)
    if user and getattr(request.state, "authenticated", False):
        headers["X-User-ID"] = user.user_id
        headers["X-User-Authenticated"] = "true"
        if user.email:
            headers["X-User-Email"] = user.email
        if user.username:
            headers["X-User-Username"] = user.username
    else:
        headers["X-User-Authenticated"] = "false"

    # =========================================================================
    # Step 6: 요청 바디 읽기 (POST, PUT, PATCH)
    # =========================================================================
    body: Optional[bytes] = None

    # GET, DELETE는 보통 body가 없고, POST/PUT/PATCH는 body가 있음
    if request.method in ["POST", "PUT", "PATCH"]:
        # 미들웨어에서 캐시된 body가 있으면 사용
        # (body는 한 번만 읽을 수 있어서 캐싱이 필요함)
        if "_cached_body" in request.scope:
            body = request.scope["_cached_body"]
        else:
            body = await request.body()

        # 디버깅용 로그 (운영에서는 제거 권장)
        logger.info(
            f"Request body length: {len(body) if body else 0}, "
            f"content: {body[:200] if body else 'None'}"
        )

    # =========================================================================
    # Step 7: Circuit Breaker 확인
    # =========================================================================
    circuit_breaker = get_circuit_breaker()

    if not circuit_breaker.can_execute(service.name):
        # Circuit이 OPEN 상태 → 즉시 실패 (빠른 실패)
        retry_after = circuit_breaker.get_retry_after(service.name)
        logger.warning(
            f"Circuit OPEN for '{service.name}', "
            f"rejecting request to {full_path}, "
            f"retry after {retry_after:.1f}s"
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "Service temporarily unavailable",
                "service": service.name,
                "retry_after": round(retry_after, 1)
            },
            headers={"Retry-After": str(int(retry_after))}
        )

    # =========================================================================
    # Step 8: 백엔드 서비스로 요청 전송 (Retry 포함)
    # =========================================================================
    logger.info(
        f"Proxying {request.method} {full_path} -> {target_url}, "
        f"headers: {dict(headers)}"
    )

    try:
        http_client = get_http_client()

        # 재시도 설정 (읽기 요청은 재시도, 쓰기 요청은 조심)
        # POST/PUT/PATCH/DELETE는 멱등성이 없으면 재시도하면 안 됨
        # 여기서는 안전을 위해 GET만 재시도
        if request.method == "GET":
            retry_config = RetryConfig(max_retries=2, base_delay=0.5)
        else:
            retry_config = RetryConfig(max_retries=0)  # 재시도 없음

        # 실제 HTTP 요청 함수
        async def make_request():
            return await http_client.request(
                method=request.method,      # GET, POST, PUT 등
                url=target_url,             # 백엔드 서비스 URL
                headers=headers,            # 전달할 헤더
                content=body,               # 요청 본문
                timeout=service.timeout     # 타임아웃 (기본 30초)
            )

        # Retry with Exponential Backoff
        response = await retry_async(make_request, config=retry_config)

        # =====================================================================
        # Step 9: 응답 처리
        # =====================================================================
        # 재시도 가능한 상태 코드면 실패로 기록 (다음 요청에 영향)
        if is_retryable_status_code(response.status_code):
            circuit_breaker.record_failure(service.name)
            logger.warning(
                f"Upstream returned {response.status_code} for {target_url}"
            )
        else:
            # 성공 (2xx, 3xx, 4xx 클라이언트 에러)
            circuit_breaker.record_success(service.name)

        # 응답 헤더 필터링 (불필요한 헤더 제거)
        response_headers = _filter_response_headers(dict(response.headers))

        # 백엔드 서비스의 응답을 그대로 클라이언트에게 반환
        return Response(
            content=response.content,               # 응답 본문
            status_code=response.status_code,       # HTTP 상태 코드
            headers=response_headers,               # 응답 헤더
            media_type=response.headers.get("content-type")  # 콘텐츠 타입
        )

    except httpx.TimeoutException as e:
        # 타임아웃 → 실패 기록
        circuit_breaker.record_failure(service.name)
        logger.error(f"Timeout for {target_url}: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Upstream service '{service.name}' timed out"
        )

    except httpx.ConnectError as e:
        # 연결 실패 → 실패 기록
        circuit_breaker.record_failure(service.name)
        logger.error(f"Connection error for {target_url}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to connect to upstream service: {service.name}"
        )

    except Exception as e:
        # 기타 예외 → 실패 기록
        circuit_breaker.record_failure(service.name)
        logger.error(f"Proxy error for {target_url}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to connect to upstream service: {service.name}"
        )


# =============================================================================
# 헬퍼 함수
# =============================================================================

def _prepare_headers(request: Request) -> dict:
    """
    📌 요청 헤더 준비

    클라이언트 요청에서 백엔드로 전달할 헤더만 추출합니다.

    Args:
        request: 원본 HTTP 요청

    Returns:
        dict: 전달할 헤더 딕셔너리

    Example:
        클라이언트 헤더:
            Authorization: Bearer xxx
            Content-Type: application/json
            Cookie: session=abc  # 전달 안 함

        반환 헤더:
            authorization: Bearer xxx
            content-type: application/json
    """
    headers = {}

    for header_name in FORWARDED_HEADERS:
        value = request.headers.get(header_name)
        if value:
            headers[header_name] = value

    return headers


def _filter_response_headers(headers: dict) -> dict:
    """
    📌 응답 헤더 필터링

    백엔드 서비스 응답에서 불필요한 헤더를 제거합니다.

    제거하는 이유:
        - transfer-encoding: Gateway에서 다시 설정됨
        - content-encoding: 압축 처리는 Gateway에서 함
        - content-length: 본문 수정 시 달라질 수 있음

    Args:
        headers: 백엔드 서비스의 응답 헤더

    Returns:
        dict: 필터링된 헤더
    """
    return {
        key: value
        for key, value in headers.items()
        if key.lower() not in EXCLUDED_RESPONSE_HEADERS
    }
