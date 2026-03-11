"""
Redis Database Module (Redis 데이터베이스 모듈)
=============================================

shared_lib의 RedisManager를 사용하여 Redis 연결을 관리합니다.

관련 파일
---------
- shared_lib/database/redis.py: 공통 Redis 연결 유틸리티
- app/core/config.py: redis_url 설정
"""

import logging
from shared_lib.database import RedisManager, get_redis_manager
from app.core.config import settings

logger = logging.getLogger(__name__)

# =============================================================================
# Redis Manager (shared_lib 사용)
# =============================================================================
_redis_manager: RedisManager = get_redis_manager()


async def init_redis():
    """Redis 연결 초기화"""
    await _redis_manager.init(settings.redis_url)
    logger.info("Redis connected")


async def close_redis():
    """Redis 연결 종료"""
    await _redis_manager.close()
    logger.info("Redis connection closed")


def get_redis():
    """Redis 클라이언트 반환"""
    return _redis_manager.client


async def check_redis_connection() -> bool:
    """Redis 연결 상태 확인"""
    return await _redis_manager.health_check()
