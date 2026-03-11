"""
=============================================================================
MySQL Database (MySQL 데이터베이스) - 공통 DB 연결 유틸
=============================================================================

📌 이 파일이 하는 일:
    SQLAlchemy를 사용한 비동기 MySQL 연결 관리를 제공합니다.
    모든 서비스에서 동일한 DB 연결 패턴을 사용할 수 있습니다.

💡 왜 공통 모듈로 분리했나요?
    1. 코드 중복 제거: 모든 서비스가 같은 연결 코드 사용
    2. 설정 일관성: 커넥션 풀 설정을 한 곳에서 관리
    3. 유지보수 용이: 연결 로직 변경 시 한 곳만 수정

🔄 연결 풀(Connection Pool)이란?
    매 요청마다 DB 연결을 새로 만들면 느립니다.
    연결을 미리 만들어두고 재사용하면 빠릅니다.

    설정 값:
    - pool_size: 기본 연결 수 (50개)
    - max_overflow: 추가 연결 수 (100개) - 트래픽 급증 시
    - pool_recycle: 3600초 (1시간마다 연결 재생성)
    - pool_timeout: 30초 (연결 대기 최대 시간)

📊 아키텍처:
    FastAPI App
        │ Depends(get_db)
        ▼
    AsyncSession (세션)
        │
        ▼
    Connection Pool (연결 풀)
        │
        ▼
    MySQL Server

사용 예시
---------
```python
from shared_lib.database import Base, create_mysql_engine, create_async_session_factory

# 1. 엔진 생성 (앱 시작 시 한 번)
engine = create_mysql_engine(settings.mysql_url, debug=settings.debug)

# 2. 세션 팩토리 생성
AsyncSessionLocal = create_async_session_factory(engine)

# 3. FastAPI 의존성 함수
async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

# 4. API에서 사용
@router.get("/users/{user_id}")
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    return await db.get(User, user_id)
```

관련 파일
---------
- user-service/app/database/mysql.py: 서비스별 DB 모듈 (이 모듈 사용)
- user-service/app/models/user.py: SQLAlchemy 모델 정의
"""

import logging
from typing import AsyncGenerator, List, Type
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import declarative_base
from sqlalchemy import text

logger = logging.getLogger(__name__)


# =============================================================================
# SQLAlchemy Base Class
# =============================================================================

Base = declarative_base()
"""
📌 SQLAlchemy 모델 기본 클래스

모든 ORM 모델은 이 클래스를 상속받습니다.

사용 예시:
    from shared_lib.database import Base

    class User(Base):
        __tablename__ = "users"
        id = Column(Integer, primary_key=True)
        email = Column(String(255), unique=True)
"""


# =============================================================================
# 엔진 및 세션 팩토리 생성 함수
# =============================================================================

def create_mysql_engine(
    mysql_url: str,
    debug: bool = False,
    pool_size: int = 50,
    max_overflow: int = 100,
    pool_recycle: int = 3600,
    pool_timeout: int = 30
) -> AsyncEngine:
    """
    📌 MySQL 비동기 엔진 생성

    SQLAlchemy 비동기 엔진을 생성합니다.
    엔진은 연결 풀을 관리하며, 애플리케이션 전체에서 하나만 생성합니다.

    Args:
        mysql_url: MySQL 연결 URL
                   형식: mysql+aiomysql://user:password@host:port/database
        debug: SQL 쿼리 로깅 여부 (개발 환경에서 True)
        pool_size: 기본 연결 풀 크기 (기본: 50)
        max_overflow: 추가 허용 연결 수 (기본: 100)
                      트래픽 급증 시 pool_size 이상으로 연결 생성
        pool_recycle: 연결 재생성 주기 (초, 기본: 3600)
                      MySQL wait_timeout 대응
        pool_timeout: 연결 대기 최대 시간 (초, 기본: 30)
                      풀이 가득 찼을 때 대기 시간

    Returns:
        AsyncEngine: SQLAlchemy 비동기 엔진

    pool_pre_ping=True 설명:
        연결 사용 전에 "SELECT 1"로 연결 유효성 검사
        "MySQL server has gone away" 에러 방지

    사용 예시:
        engine = create_mysql_engine(
            mysql_url="mysql+aiomysql://user:pass@localhost/db",
            debug=True  # SQL 쿼리 로깅 활성화
        )
    """
    return create_async_engine(
        mysql_url,
        echo=debug,           # SQL 쿼리 로깅
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=pool_recycle,
        pool_pre_ping=True,   # 연결 유효성 사전 검사
        pool_timeout=pool_timeout,
    )


def create_async_session_factory(engine: AsyncEngine) -> async_sessionmaker:
    """
    📌 비동기 세션 팩토리 생성

    세션 팩토리는 세션 객체를 생성하는 "공장"입니다.
    필요할 때마다 세션을 만들어서 사용합니다.

    Args:
        engine: SQLAlchemy 비동기 엔진

    Returns:
        async_sessionmaker: 세션 팩토리

    expire_on_commit=False 설명:
        커밋 후에도 객체 속성에 접근 가능
        추가 쿼리 없이 응답에 데이터를 포함할 수 있음

    사용 예시:
        AsyncSessionLocal = create_async_session_factory(engine)

        async with AsyncSessionLocal() as session:
            user = await session.get(User, 1)
            await session.commit()
            return user.email  # expire_on_commit=False여야 가능
    """
    return async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False  # 커밋 후에도 객체 속성 접근 가능
    )


def get_db_dependency(session_factory: async_sessionmaker):
    """
    📌 FastAPI 의존성 함수 생성

    Depends()에 전달할 의존성 함수를 생성합니다.
    세션 생명주기(시작-사용-종료)를 자동 관리합니다.

    Args:
        session_factory: 세션 팩토리

    Returns:
        get_db 함수: FastAPI Depends()에 사용

    생명주기:
        1. 요청 시작 → 세션 생성
        2. API 핸들러 실행
        3. 예외 발생 시 → 롤백
        4. 요청 종료 → 세션 닫기

    사용 예시:
        # 서비스에서 한 번 생성
        get_db = get_db_dependency(AsyncSessionLocal)

        # API에서 사용
        @router.get("/users/{id}")
        async def get_user(id: int, db: AsyncSession = Depends(get_db)):
            return await db.get(User, id)
    """
    async def get_db() -> AsyncGenerator[AsyncSession, None]:
        async with session_factory() as session:
            try:
                yield session
            except Exception as e:
                # 에러 발생 시 트랜잭션 롤백
                await session.rollback()
                logger.error(f"Database session error: {e}")
                raise
            finally:
                # 항상 세션 닫기
                await session.close()

    return get_db


# =============================================================================
# 생명주기 관리 함수
# =============================================================================

async def init_database(engine: AsyncEngine, models: List[Type] = None):
    """
    📌 데이터베이스 초기화 (테이블 생성)

    애플리케이션 시작 시 호출하여 테이블을 생성합니다.

    Args:
        engine: SQLAlchemy 비동기 엔진
        models: 등록할 모델 클래스 목록 (import 트리거용)
                모델을 import해야 Base.metadata에 등록됨

    DDL 전략:
        create_all()은 IF NOT EXISTS를 사용
        기존 테이블에 영향을 주지 않음

    ⚠️ 프로덕션 참고:
        스키마 변경은 Alembic 마이그레이션 사용 권장
        create_all()은 새 테이블만 생성 (변경 불가)

    사용 예시:
        from app.models.user import User  # import하면 Base.metadata에 등록됨
        await init_database(engine)
    """
    try:
        async with engine.begin() as conn:
            # 모든 테이블 생성 (IF NOT EXISTS)
            await conn.run_sync(Base.metadata.create_all)
        logger.info("MySQL database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize MySQL database: {e}")
        raise


async def check_connection(engine: AsyncEngine) -> bool:
    """
    📌 데이터베이스 연결 확인

    Health Check 엔드포인트에서 사용합니다.
    가장 가벼운 쿼리(SELECT 1)로 연결 상태를 확인합니다.

    Args:
        engine: SQLAlchemy 비동기 엔진

    Returns:
        bool: 연결 성공 시 True, 실패 시 False

    사용 예시:
        @router.get("/health")
        async def health():
            is_healthy = await check_connection(engine)
            return {"mysql": "healthy" if is_healthy else "unhealthy"}
    """
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            return result.fetchone() is not None
    except Exception as e:
        logger.error(f"MySQL connection check failed: {e}")
        return False


async def close_database(engine: AsyncEngine):
    """
    📌 데이터베이스 연결 종료

    애플리케이션 종료 시 호출하여 연결 풀을 정리합니다.

    Args:
        engine: SQLAlchemy 비동기 엔진

    ⚠️ 중요:
        Graceful Shutdown을 위해 반드시 호출해야 합니다.
        미호출 시 연결 리소스 누수 발생 가능.
    """
    await engine.dispose()
    logger.info("MySQL database connections closed")
