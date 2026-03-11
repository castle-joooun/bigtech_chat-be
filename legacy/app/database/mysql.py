"""
MySQL 데이터베이스 연결 설정 (MySQL Database Connection Configuration)

================================================================================
아키텍처 개요 (Architecture Overview)
================================================================================

이 모듈은 SQLAlchemy를 사용한 MySQL 비동기 연결을 관리합니다.
FastAPI의 비동기 특성에 맞춰 aiomysql 드라이버를 사용하고,
커넥션 풀링을 통해 데이터베이스 연결을 효율적으로 관리합니다.

핵심 구성요소:
- AsyncEngine: 비동기 DB 엔진 (연결 풀 포함)
- AsyncSession: 비동기 DB 세션 (ORM 작업 단위)
- Base: SQLAlchemy 모델의 기반 클래스

================================================================================
커넥션 풀링 (Connection Pooling)
================================================================================

커넥션 풀이 필요한 이유:
1. 연결 생성 비용: TCP 핸드셰이크, 인증, 세션 초기화 (~50ms)
2. 연결 제한: MySQL max_connections 설정 준수
3. 리소스 관리: 메모리, 파일 디스크립터 절약

풀 크기 결정 공식:
- pool_size = (core_count * 2) + effective_spindle_count
- 일반적으로 10-20 정도가 적절
- 너무 크면: 메모리 낭비, 연결 경쟁
- 너무 작으면: 대기 시간 증가

================================================================================
적용된 디자인 패턴 (Design Patterns Applied)
================================================================================

1. Factory Pattern (팩토리 패턴)
   - create_async_engine(): 엔진 객체 생성
   - async_sessionmaker(): 세션 객체 생성 팩토리

2. Dependency Injection Pattern (의존성 주입 패턴)
   - get_db(): FastAPI의 Depends()와 함께 사용
   - 테스트 시 Mock 세션 주입 가능

3. Context Manager Pattern (컨텍스트 매니저 패턴)
   - async with AsyncSessionLocal() as session
   - 자동 리소스 정리 (close)

4. Singleton Pattern (싱글톤 패턴)
   - engine: 애플리케이션 전역에서 하나의 인스턴스
   - 풀 연결 재사용

================================================================================
SOLID 원칙 적용 (SOLID Principles)
================================================================================

1. Single Responsibility Principle (단일 책임 원칙)
   - 이 모듈: DB 연결 관리만 담당
   - 모델 정의는 app/models/에 분리

2. Open/Closed Principle (개방-폐쇄 원칙)
   - 설정 변경은 config.py에서
   - 코드 수정 없이 환경 변수로 설정 변경

3. Dependency Inversion Principle (의존성 역전 원칙)
   - settings 객체를 통한 설정 주입
   - 상위 모듈이 하위 모듈에 의존하지 않음

================================================================================
성능 최적화 설정 (Performance Optimization Settings)
================================================================================

1. pool_use_lifo=True
   - LIFO (Last In, First Out) 방식
   - 최근 사용된 연결 재사용 → 캐시 히트율 증가
   - 연결당 서버 측 세션 상태 활용

2. pool_pre_ping=True
   - 연결 사용 전 유효성 검사
   - "MySQL server has gone away" 에러 방지
   - 약간의 오버헤드 있지만 안정성 향상

3. pool_recycle=1800
   - 30분마다 연결 재생성
   - MySQL wait_timeout 대비 (기본 8시간)
   - 메모리 누수 방지

4. autoflush=False
   - 자동 플러시 비활성화
   - 명시적 commit()으로 제어
   - 불필요한 DB 왕복 방지

================================================================================
"""

from typing import AsyncGenerator, Dict, Any
import logging
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text, event
from sqlalchemy.pool import AsyncAdaptedQueuePool
from legacy.app.core.config import settings


# =============================================================================
# SQLAlchemy Base 클래스 (Declarative Base)
# =============================================================================
#
# 모든 ORM 모델의 기반 클래스
# 메타데이터를 통해 테이블 스키마 정보 관리
#
# 사용 예시:
# ```python
# from legacy.app.database.mysql import Base
#
# class User(Base):
#     __tablename__ = "users"
#     id = Column(Integer, primary_key=True)
#     ...
# ```
#
# =============================================================================

Base = declarative_base()


# =============================================================================
# 비동기 DB 엔진 생성 (Async Database Engine)
# =============================================================================
#
# create_async_engine() 주요 파라미터:
#
# 1. URL 형식:
#    mysql+aiomysql://user:password@host:port/database
#
# 2. 풀 관련 설정:
#    - poolclass: 풀 구현체 (AsyncAdaptedQueuePool)
#    - pool_size: 기본 연결 수
#    - max_overflow: 추가 연결 허용 수
#    - pool_timeout: 연결 대기 타임아웃
#    - pool_recycle: 연결 재활용 주기
#    - pool_pre_ping: 사용 전 연결 검사
#
# 3. 성능 최적화:
#    - pool_use_lifo: LIFO 방식 연결 재사용
#    - echo: SQL 쿼리 로깅 (디버그용)
#
# =============================================================================

engine = create_async_engine(
    settings.mysql_url,

    # -------------------------------------------------------------------------
    # 디버그 설정
    # -------------------------------------------------------------------------
    echo=settings.debug,  # True면 SQL 쿼리를 로그에 출력

    # -------------------------------------------------------------------------
    # 커넥션 풀 클래스
    #
    # AsyncAdaptedQueuePool:
    # - 비동기 환경에서 동기 QueuePool을 래핑
    # - FIFO/LIFO 방식 지원
    # - 스레드 안전
    # -------------------------------------------------------------------------
    poolclass=AsyncAdaptedQueuePool,

    # -------------------------------------------------------------------------
    # 풀 크기 설정
    #
    # pool_size: 기본적으로 유지할 연결 수
    # max_overflow: pool_size 초과 시 추가 허용 연결 수
    # 최대 연결 수 = pool_size + max_overflow = 10 + 20 = 30
    #
    # 결정 기준:
    # - 동시 요청 수 예측
    # - MySQL max_connections 설정
    # - 서버 리소스 (메모리, CPU)
    # -------------------------------------------------------------------------
    pool_size=10,       # 기본 연결 수
    max_overflow=20,    # 최대 추가 연결 수

    # -------------------------------------------------------------------------
    # 연결 재활용 (Connection Recycling)
    #
    # pool_recycle: N초 후 연결 재생성
    # 1800초 = 30분
    #
    # 필요한 이유:
    # - MySQL wait_timeout (기본 8시간) 대비
    # - 방화벽 idle timeout 대비
    # - 메모리 누수 방지
    #
    # 주의: 활성 트랜잭션 중에는 재활용 안 됨
    # -------------------------------------------------------------------------
    pool_recycle=1800,

    # -------------------------------------------------------------------------
    # 연결 유효성 검사 (Pre-ping)
    #
    # pool_pre_ping=True:
    # - 풀에서 연결을 가져올 때 SELECT 1 실행
    # - 연결이 끊어졌으면 새 연결 생성
    #
    # 장점:
    # - "MySQL server has gone away" 에러 방지
    # - 안정적인 연결 보장
    #
    # 단점:
    # - 약간의 오버헤드 (연결당 1 쿼리 추가)
    # -------------------------------------------------------------------------
    pool_pre_ping=True,

    # -------------------------------------------------------------------------
    # 연결 대기 타임아웃
    #
    # pool_timeout: 풀에서 연결을 기다리는 최대 시간 (초)
    # 초과 시 TimeoutError 발생
    #
    # 적절한 값:
    # - 너무 짧으면: 피크 시간에 에러 빈발
    # - 너무 길면: 요청 대기 시간 증가
    # -------------------------------------------------------------------------
    pool_timeout=30,

    # -------------------------------------------------------------------------
    # LIFO 방식 연결 재사용
    #
    # pool_use_lifo=True:
    # - Last In, First Out 방식
    # - 가장 최근에 반환된 연결을 먼저 사용
    #
    # 장점:
    # - 연결당 서버 측 캐시 활용
    # - "Hot" 연결 재사용으로 성능 향상
    # - 사용되지 않는 연결은 자연스럽게 timeout
    #
    # 참고:
    # - 기본값은 FIFO (False)
    # - FIFO: 연결 간 부하 분산, 연결 수명 균등화
    # -------------------------------------------------------------------------
    pool_use_lifo=True,

    # -------------------------------------------------------------------------
    # 연결 인자 (Connection Arguments)
    #
    # aiomysql/PyMySQL에 전달되는 추가 옵션
    # -------------------------------------------------------------------------
    connect_args={
        "connect_timeout": 10,  # 연결 수립 타임아웃 (초)
        "read_timeout": 30,     # 쿼리 읽기 타임아웃 (초)
        "write_timeout": 30,    # 쿼리 쓰기 타임아웃 (초)
    }
)


# =============================================================================
# 비동기 세션 팩토리 (Async Session Factory)
# =============================================================================
#
# async_sessionmaker: 세션 객체를 생성하는 팩토리 클래스
#
# 세션의 역할:
# 1. ORM 객체와 DB 간의 동기화
# 2. 트랜잭션 경계 관리
# 3. 쿼리 실행 및 결과 매핑
#
# 주요 설정:
# - expire_on_commit=False: 커밋 후에도 객체 속성 유지
# - autoflush=False: 자동 플러시 비활성화 (명시적 제어)
#
# =============================================================================

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,

    # -------------------------------------------------------------------------
    # expire_on_commit=False
    #
    # True (기본값):
    # - commit() 후 모든 객체의 속성이 만료됨
    # - 다음 속성 접근 시 DB에서 새로 조회
    #
    # False (현재 설정):
    # - commit() 후에도 객체 속성 유지
    # - 추가 DB 조회 없이 객체 사용 가능
    #
    # 사용 예시:
    # ```python
    # user = User(name="John")
    # db.add(user)
    # await db.commit()
    # print(user.name)  # False: "John" 출력, True: DB 조회 필요
    # ```
    # -------------------------------------------------------------------------
    expire_on_commit=False,

    # -------------------------------------------------------------------------
    # autoflush=False
    #
    # True (기본값):
    # - 쿼리 실행 전 자동으로 flush() 호출
    # - 아직 커밋되지 않은 변경사항을 DB에 반영
    #
    # False (현재 설정):
    # - 명시적 flush() 호출 필요
    # - 불필요한 DB 왕복 방지
    # - 트랜잭션 타이밍 명확하게 제어
    #
    # 주의: 복잡한 쿼리에서 의도치 않은 동작 방지
    # -------------------------------------------------------------------------
    autoflush=False,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 데이터베이스 세션 의존성 (Database Session Dependency)
# =============================================================================

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI 의존성 주입을 위한 DB 세션 제공자

    =========================================================================
    Dependency Injection Pattern
    =========================================================================

    FastAPI의 Depends()와 함께 사용:
    ```python
    @app.get("/users/{user_id}")
    async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
        user = await db.get(User, user_id)
        return user
    ```

    =========================================================================
    Context Manager 동작
    =========================================================================

    1. async with AsyncSessionLocal() as session:
       - 세션 객체 생성
       - 풀에서 연결 획득

    2. yield session:
       - 호출자에게 세션 제공
       - 요청 처리

    3. finally:
       - 에러 발생 시 rollback()
       - 세션 close()
       - 연결을 풀에 반환

    =========================================================================
    트랜잭션 관리
    =========================================================================

    기본적으로 autocommit=False
    - 명시적 commit() 필요
    - 에러 시 자동 rollback

    Yields:
        AsyncSession: 비동기 DB 세션

    Example:
        >>> async with get_db() as db:
        ...     user = User(name="John")
        ...     db.add(user)
        ...     await db.commit()
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as e:
            # 에러 발생 시 롤백
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            # 세션 정리 (연결 반환)
            await session.close()


# 명명 규칙 일관성을 위한 별칭
get_async_session = get_db


# =============================================================================
# 데이터베이스 초기화 (Database Initialization)
# =============================================================================

async def init_mysql_db():
    """
    MySQL 데이터베이스 초기화 (테이블 생성)

    =========================================================================
    동작 흐름
    =========================================================================

    1. 모든 모델 import (메타데이터 등록)
    2. engine.begin()으로 트랜잭션 시작
    3. Base.metadata.create_all()로 테이블 생성
    4. 이미 존재하는 테이블은 건너뜀

    =========================================================================
    주의사항
    =========================================================================

    1. 프로덕션 환경:
       - 마이그레이션 도구 사용 권장 (Alembic)
       - create_all()은 스키마 변경 불가

    2. 테스트 환경:
       - 테스트 전 create_all()
       - 테스트 후 drop_all()

    =========================================================================
    모델 Import 필요성
    =========================================================================

    SQLAlchemy는 Python 클래스가 import되어야 메타데이터에 등록됨
    따라서 모든 모델을 명시적으로 import

    Raises:
        Exception: DB 연결 실패 또는 테이블 생성 실패

    Example:
        >>> # 애플리케이션 시작 시
        >>> await init_mysql_db()
    """
    try:
        # ---------------------------------------------------------------------
        # 모든 모델 import
        #
        # 이 import문이 실행되면 각 모델 클래스가
        # Base.metadata에 테이블 정보를 등록함
        # ---------------------------------------------------------------------
        from legacy.app.models import (
            User, ChatRoom, RoomMember, Friendship
        )

        async with engine.begin() as conn:
            # -----------------------------------------------------------------
            # 테이블 생성
            #
            # run_sync(): 동기 함수를 비동기로 실행
            # create_all(): 등록된 모든 테이블 생성
            # checkfirst=True (기본값): 존재하는 테이블 건너뜀
            # -----------------------------------------------------------------
            await conn.run_sync(Base.metadata.create_all)

        logger.info("MySQL database initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize MySQL database: {e}")
        raise


# =============================================================================
# 연결 상태 확인 (Connection Health Check)
# =============================================================================

async def check_mysql_connection():
    """
    MySQL 데이터베이스 연결 상태 확인

    =========================================================================
    사용 시나리오
    =========================================================================

    1. 헬스체크 API (/health)
    2. 애플리케이션 시작 시 연결 확인
    3. 모니터링 시스템에서 주기적 확인

    =========================================================================
    SELECT 1 사용 이유
    =========================================================================

    - 가장 가벼운 쿼리
    - 테이블 접근 불필요
    - 연결 상태만 확인

    Returns:
        bool: 연결 성공 여부

    Example:
        >>> if await check_mysql_connection():
        ...     print("MySQL 연결 정상")
        ... else:
        ...     print("MySQL 연결 실패")
    """
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            return result.fetchone() is not None
    except Exception as e:
        logger.error(f"MySQL connection check failed: {e}")
        return False


# =============================================================================
# 데이터베이스 연결 종료 (Database Connection Cleanup)
# =============================================================================

async def close_mysql_db():
    """
    MySQL 데이터베이스 연결 종료

    =========================================================================
    동작 내용
    =========================================================================

    engine.dispose():
    1. 풀의 모든 연결 닫기
    2. 풀 자체 해제
    3. 이후 새 요청 시 새 풀 생성

    =========================================================================
    호출 시점
    =========================================================================

    - 애플리케이션 종료 시 (shutdown 이벤트)
    - Graceful shutdown 과정에서

    =========================================================================
    주의사항
    =========================================================================

    dispose() 후에도 engine은 재사용 가능
    새 연결 요청 시 풀이 다시 생성됨

    Example:
        >>> # 애플리케이션 종료 시
        >>> await close_mysql_db()
    """
    await engine.dispose()
    logger.info("MySQL database connections closed")


# =============================================================================
# 커넥션 풀 모니터링 (Connection Pool Monitoring)
# =============================================================================

async def get_pool_status() -> Dict[str, Any]:
    """
    MySQL 커넥션 풀 상태 조회 (모니터링용)

    =========================================================================
    반환 정보
    =========================================================================

    - pool_size: 현재 풀 크기 (설정된 pool_size)
    - checked_in: 풀에 반환된 연결 수 (대기 중)
    - checked_out: 현재 사용 중인 연결 수
    - overflow: 초과 생성된 연결 수 (max_overflow 내)
    - invalidated: 무효화된 연결 수

    =========================================================================
    모니터링 지표
    =========================================================================

    1. checked_out 높음:
       - 동시 요청이 많음
       - pool_size 증가 고려

    2. overflow 높음:
       - 피크 시간대 부하
       - max_overflow 증가 또는 쿼리 최적화

    3. invalidated 높음:
       - 연결 문제 발생
       - pool_pre_ping 확인

    =========================================================================
    사용 예시
    =========================================================================

    ```python
    # 헬스체크 API에서
    @app.get("/health")
    async def health():
        pool_status = await get_pool_status()
        return {
            "status": "healthy",
            "mysql_pool": pool_status
        }
    ```

    Returns:
        Dict[str, Any]: 풀 상태 정보

    Example:
        >>> status = await get_pool_status()
        >>> print(f"사용 중: {status['checked_out']}")
        >>> print(f"대기 중: {status['checked_in']}")
    """
    pool = engine.pool
    return {
        "pool_size": pool.size(),           # 설정된 풀 크기
        "checked_in": pool.checkedin(),     # 풀에 있는 연결 수
        "checked_out": pool.checkedout(),   # 사용 중인 연결 수
        "overflow": pool.overflow(),        # 초과 생성된 연결 수
        "invalidated": pool.invalidated()   # 무효화된 연결 수
    }
