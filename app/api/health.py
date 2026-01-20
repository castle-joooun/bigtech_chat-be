from fastapi import APIRouter, HTTPException
from datetime import datetime
from app.database import check_database_health, get_redis
from app.database.redis import set_cache, get_cache, get_stats

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
