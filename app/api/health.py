from fastapi import APIRouter, HTTPException
from datetime import datetime
from app.database import check_database_health

router = APIRouter()


@router.get("/health")
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
                "mongodb": "connected" if db_health["mongodb"] else "disconnected"
            },
            "service": "bigtech-chat-backend"
        }
    except Exception as e:
        raise HTTPException(
            status_code=503, 
            detail=f"Health check failed: {str(e)}"
        )


@router.get("/health/ready")
async def readiness_check():
    """Kubernetes readiness probe endpoint"""
    db_health = await check_database_health()
    
    if not db_health["overall"]:
        raise HTTPException(
            status_code=503,
            detail="Service not ready - database connections failed"
        )
    
    return {"status": "ready"}


@router.get("/health/live")
async def liveness_check():
    """Kubernetes liveness probe endpoint"""
    return {"status": "alive", "timestamp": datetime.utcnow()}
