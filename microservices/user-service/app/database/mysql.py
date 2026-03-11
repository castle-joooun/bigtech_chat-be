"""
MySQL Database Module (MySQL 데이터베이스 모듈)
=============================================

shared_lib의 공통 DB 유틸리티를 사용하여 MySQL 연결을 관리합니다.

User Service는 User 데이터의 유일한 소유자입니다.

아키텍처 개요
-------------
```
┌─────────────────────────────────────────────────────────────┐
│                       FastAPI App                            │
│                                                              │
│  @app.get("/users/{id}")                                    │
│  async def get_user(db: AsyncSession = Depends(get_db)):    │
│      return await db.get(User, id)                          │
└──────────────────────────┬──────────────────────────────────┘
                           │ Depends(get_db)
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                    Connection Pool                           │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐ ... (pool_size=50)       │
│  │ Conn│ │ Conn│ │ Conn│ │ Conn│                          │
│  └─────┘ └─────┘ └─────┘ └─────┘                          │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                       MySQL Server                           │
│  Database: bigtech_chat                                     │
│  Tables: users                                              │
└─────────────────────────────────────────────────────────────┘
```

관련 파일
---------
- shared_lib/database/mysql.py: 공통 DB 연결 유틸리티
- app/core/config.py: mysql_url 설정
- app/models/user.py: User SQLAlchemy 모델
"""

import logging
from shared_lib.database import (
    Base,
    create_mysql_engine,
    create_async_session_factory,
    get_db_dependency,
    init_database,
    close_database,
    check_connection,
)
from app.core.config import settings

logger = logging.getLogger(__name__)

# =============================================================================
# Database Engine & Session Factory (shared_lib 사용)
# =============================================================================
engine = create_mysql_engine(
    settings.mysql_url,
    debug=settings.debug,
    pool_size=50,
    max_overflow=100,
    pool_recycle=3600,
    pool_timeout=30,
)

AsyncSessionLocal = create_async_session_factory(engine)

# FastAPI Dependency
get_db = get_db_dependency(AsyncSessionLocal)
get_async_session = get_db  # Alias


# =============================================================================
# Lifecycle Functions
# =============================================================================
async def init_mysql_db():
    """
    MySQL 데이터베이스 초기화

    User Service는 User 모델의 유일한 소유자입니다.
    """
    try:
        # Import models to register with Base.metadata
        from app.models.user import User

        await init_database(engine)
        logger.info("MySQL database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize MySQL database: {e}")
        raise


async def check_mysql_connection() -> bool:
    """MySQL 연결 상태 확인"""
    return await check_connection(engine)


async def close_mysql_db():
    """MySQL 연결 풀 종료"""
    await close_database(engine)
