"""
=============================================================================
Health Check Router - 서비스 상태 확인 API
=============================================================================

📌 이 파일이 하는 일:
    API Gateway와 백엔드 서비스들의 상태를 확인하는 API를 제공합니다.
    모니터링 시스템(Kubernetes, Prometheus 등)이 이 API를 호출해서
    서비스가 정상인지 확인합니다.

💡 왜 헬스 체크가 필요한가요?
    1. 자동 복구: 서비스가 죽으면 Kubernetes가 자동으로 재시작
    2. 로드밸런싱: 비정상 서비스로 트래픽 안 보냄
    3. 모니터링: 서비스 상태를 대시보드에서 실시간 확인
    4. 배포: 새 버전 배포 시 정상 여부 확인 후 트래픽 전환

🔄 Kubernetes 헬스 체크 종류:
    - Liveness Probe: 살아있나? → 죽었으면 재시작
    - Readiness Probe: 요청 받을 준비 됐나? → 안 됐으면 트래픽 안 보냄

📊 제공하는 엔드포인트:
    - GET /health: Gateway 자체 상태 (Liveness)
    - GET /health/services: Gateway + 모든 백엔드 서비스 상태 (전체 시스템)
"""

import logging
from typing import Dict, Any
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from ..registry import get_registry
from ..utils.http_client import get_http_client
from ..utils.circuit_breaker import get_circuit_breaker


logger = logging.getLogger("api-gateway.health")

# FastAPI 라우터 (태그는 API 문서에서 그룹화용)
router = APIRouter(tags=["Health"])


# =============================================================================
# 헬스 체크 엔드포인트
# =============================================================================

@router.get("/health")
async def health_check() -> Dict[str, str]:
    """
    📌 Gateway 헬스 체크 (단순 버전)

    Gateway 자체가 살아있는지만 확인합니다.
    Kubernetes Liveness Probe가 이 엔드포인트를 호출합니다.

    Returns:
        dict: {"status": "healthy", "service": "api-gateway"}

    💡 이 API가 응답하면 Gateway는 살아있는 것입니다.
       백엔드 서비스 상태는 확인하지 않습니다.

    사용 예시:
        curl http://localhost:8000/health
        # → {"status": "healthy", "service": "api-gateway"}
    """
    return {
        "status": "healthy",
        "service": "api-gateway"
    }


@router.get("/health/services")
async def services_health_check() -> JSONResponse:
    """
    📌 전체 시스템 헬스 체크 (상세 버전)

    Gateway와 모든 백엔드 서비스의 상태를 확인합니다.
    모니터링 대시보드나 운영 확인용으로 사용합니다.

    Returns:
        JSONResponse: 모든 서비스의 상태 정보

    응답 예시 (모두 정상):
        HTTP 200
        {
            "gateway": "healthy",
            "services": {
                "user": {"status": "healthy", "url": "http://user-service:8005"},
                "friend": {"status": "healthy", "url": "http://friend-service:8003"},
                "chat": {"status": "healthy", "url": "http://chat-service:8002"}
            }
        }

    응답 예시 (일부 장애):
        HTTP 503
        {
            "gateway": "healthy",
            "services": {
                "user": {"status": "healthy", "url": "..."},
                "friend": {"status": "unreachable", "url": "...", "error": "Connection refused"},
                "chat": {"status": "unhealthy", "url": "...", "error": "Status code: 500"}
            }
        }

    💡 상태 종류:
        - healthy: 정상 (200 OK 응답)
        - unhealthy: 비정상 응답 (500 등)
        - unreachable: 연결 불가 (서비스 다운)
    """
    # 서비스 레지스트리에서 모든 서비스 정보 가져오기
    registry = get_registry()
    services = registry.get_all_services()
    http_client = get_http_client()

    # 결과를 저장할 딕셔너리
    results: Dict[str, Any] = {
        "gateway": "healthy",   # Gateway는 이 코드가 실행되면 살아있는 것
        "services": {}
    }

    all_healthy = True  # 모든 서비스가 정상인지 추적

    # =========================================================================
    # 각 백엔드 서비스의 /health 엔드포인트 호출
    # =========================================================================
    for service_key, service_info in services.items():
        try:
            # 백엔드 서비스의 헬스 체크 엔드포인트 호출
            # 예: http://user-service:8005/health
            response = await http_client.get(
                f"{service_info.url}/health",
                timeout=5.0  # 5초 안에 응답 없으면 실패
            )

            if response.status_code == 200:
                # ✅ 정상: 200 OK 응답
                results["services"][service_key] = {
                    "status": "healthy",
                    "url": service_info.url
                }
            else:
                # ⚠️ 비정상: 200이 아닌 응답 (500, 503 등)
                results["services"][service_key] = {
                    "status": "unhealthy",
                    "url": service_info.url,
                    "error": f"Status code: {response.status_code}"
                }
                all_healthy = False

        except Exception as e:
            # ❌ 연결 실패: 네트워크 오류, 서비스 다운 등
            results["services"][service_key] = {
                "status": "unreachable",
                "url": service_info.url,
                "error": str(e)  # 에러 메시지 포함
            }
            all_healthy = False
            logger.warning(f"Health check failed for {service_key}: {e}")

    # =========================================================================
    # 응답 상태 코드 결정
    # =========================================================================
    # 모두 정상: 200 OK
    # 하나라도 비정상: 503 Service Unavailable
    status_code = status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE

    return JSONResponse(
        status_code=status_code,
        content=results
    )


@router.get("/health/circuits")
async def circuit_breaker_status() -> Dict[str, Any]:
    """
    📌 Circuit Breaker 상태 조회

    모든 서비스의 Circuit Breaker 상태를 확인합니다.
    운영/모니터링 대시보드에서 사용합니다.

    Returns:
        dict: 각 서비스의 Circuit Breaker 상태

    응답 예시:
        {
            "user-service": {
                "state": "closed",      # 정상
                "failure_count": 0,
                "retry_after": 0.0
            },
            "friend-service": {
                "state": "open",        # 차단됨
                "failure_count": 5,
                "retry_after": 45.2     # 45초 후 재시도 가능
            },
            "chat-service": {
                "state": "half_open",   # 테스트 중
                "failure_count": 5,
                "retry_after": 0.0
            }
        }

    💡 상태 설명:
        - closed: 정상 상태, 요청 허용
        - open: 차단 상태, 요청 거부 (빠른 실패)
        - half_open: 테스트 상태, 일부 요청 허용하여 복구 확인

    사용 예시:
        curl http://localhost:8000/health/circuits
    """
    circuit_breaker = get_circuit_breaker()
    return circuit_breaker.get_all_states()
