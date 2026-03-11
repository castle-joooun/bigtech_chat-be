"""
헬스 체크 API 엔드포인트 (Health Check API Endpoints)

================================================================================
아키텍처 개요 (Architecture Overview)
================================================================================
애플리케이션 상태 확인을 위한 FastAPI 라우터입니다.
Kubernetes 헬스 프로브 및 모니터링 시스템에서 사용됩니다.

헬스 체크 종류:
    ├── /health: 전체 상태 (데이터베이스 연결 포함)
    ├── /health/ready: Readiness Probe (서비스 준비 상태)
    ├── /health/live: Liveness Probe (서비스 생존 상태)
    └── /health/redis: Redis 상세 상태

================================================================================
Kubernetes 프로브 설정 예시
================================================================================
livenessProbe:
  httpGet:
    path: /health/live
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8000
  initialDelaySeconds: 5
  periodSeconds: 5

================================================================================
API 엔드포인트 (API Endpoints)
================================================================================
- GET /health: 전체 시스템 상태
- GET /health/ready: 서비스 준비 상태 (Kubernetes Readiness)
- GET /health/live: 서비스 생존 상태 (Kubernetes Liveness)
- GET /health/redis: Redis 상세 상태
- POST /health/redis/test: Redis 기본 동작 테스트
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime
from legacy.app.database import check_database_health, get_redis
from legacy.app.database.redis import set_cache, get_cache, get_stats

router = APIRouter(
    prefix='/health',
    tags=['health']
)


@router.get("")
async def health_check():
    """Application health check endpoint"""
    try:
        db_health = await check_database_health()
        
        overall_status = "healthy" if db_health["overall"] else "unhealthy"
        
        return {
            "status": overall_status,
            "timestamp": datetime.utcnow(),
            "databases": {
                "mysql": "connected" if db_health["mysql"] else "disconnected",
                "mongodb": "connected" if db_health["mongodb"] else "disconnected",
                "redis": db_health["redis"]
            },
            "service": "bigtech-chat-backend"
        }
    except Exception as e:
        raise HTTPException(
            status_code=503, 
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/ready")
async def readiness_check():
    """Kubernetes readiness probe endpoint"""
    db_health = await check_database_health()
    
    if not db_health["overall"]:
        raise HTTPException(
            status_code=503,
            detail="Service not ready - database connections failed"
        )
    
    return {"status": "ready"}


@router.get("/live")
async def liveness_check():
    """Kubernetes liveness probe endpoint"""
    return {"status": "alive", "timestamp": datetime.utcnow()}


@router.get("/redis")
async def redis_health():
    """Redis 상세 상태 확인"""
    try:
        stats = await get_stats()
        return {
            "status": "healthy",
            "stats": stats,
            "timestamp": datetime.utcnow()
        }
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Redis health check failed: {str(e)}"
        )


@router.post("/redis/test")
async def test_redis_operations():
    """Redis 기본 동작 테스트 (set/get)"""
    try:
        test_key = "health_check_test"
        test_value = f"test_value_{datetime.utcnow().isoformat()}"

        # Set 테스트
        set_result = await set_cache(test_key, test_value, 30)  # 30초 TTL

        # Get 테스트
        get_result = await get_cache(test_key)

        # 결과 검증
        if get_result == test_value:
            return {
                "status": "success",
                "message": "Redis set/get operations working correctly",
                "test_data": {
                    "key": test_key,
                    "value_set": test_value,
                    "value_retrieved": get_result,
                    "set_success": set_result
                },
                "timestamp": datetime.utcnow()
            }
        else:
            return {
                "status": "error",
                "message": "Redis get operation returned unexpected value",
                "test_data": {
                    "expected": test_value,
                    "actual": get_result
                }
            }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Redis test failed: {str(e)}"
        )
