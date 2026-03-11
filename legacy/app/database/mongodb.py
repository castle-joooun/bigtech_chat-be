"""
MongoDB 데이터베이스 연결 설정 (MongoDB Database Connection Configuration)

================================================================================
아키텍처 개요 (Architecture Overview)
================================================================================

이 모듈은 Motor(비동기 MongoDB 드라이버)와 Beanie(ODM)를 사용하여
MongoDB 연결을 관리합니다. 채팅 메시지와 같은 비정형 데이터 저장에 적합합니다.

핵심 구성요소:
- AsyncIOMotorClient: 비동기 MongoDB 클라이언트
- AsyncIOMotorDatabase: 비동기 데이터베이스 인스턴스
- Beanie: 비동기 ODM (Object Document Mapper)

MongoDB 선택 이유:
- 채팅 메시지의 유연한 스키마 (첨부파일, 반응 등)
- 높은 쓰기 처리량 (초당 수만 건의 메시지)
- 수평 확장 용이 (샤딩)
- 시계열 데이터에 적합

================================================================================
Motor vs PyMongo
================================================================================

PyMongo: 동기 드라이버
- 블로킹 I/O
- 스레드 기반 동시성

Motor: 비동기 드라이버 (현재 사용)
- 논블로킹 I/O
- asyncio 기반 동시성
- FastAPI, aiohttp 등과 호환

================================================================================
Beanie ODM
================================================================================

Beanie의 역할:
1. Python 클래스를 MongoDB 문서에 매핑
2. 타입 힌트와 Pydantic 모델 활용
3. 인덱스 자동 생성
4. 편리한 쿼리 인터페이스

Beanie vs Motor 직접 사용:
- Beanie: 타입 안전, 편리한 API, 약간의 오버헤드
- Motor 직접: 더 낮은 수준, 더 유연함, 더 많은 코드

================================================================================
적용된 디자인 패턴 (Design Patterns Applied)
================================================================================

1. Singleton Pattern (싱글톤 패턴)
   - client, database: 전역 단일 인스턴스
   - 모듈 수준에서 관리

2. Factory Pattern (팩토리 패턴)
   - AsyncIOMotorClient(): 클라이언트 생성
   - init_beanie(): ODM 초기화

3. Global Object Pattern (전역 객체 패턴)
   - get_database(): 전역 database 인스턴스 반환
   - 애플리케이션 전역에서 접근 가능

================================================================================
커넥션 풀 설정 (Connection Pool Configuration)
================================================================================

MongoDB 커넥션 풀 특징:
- 내장 커넥션 풀 (별도 설정 불필요)
- 기본값: minPoolSize=0, maxPoolSize=100
- LIFO 방식 (최근 연결 재사용)

최적화 설정:
- maxPoolSize=20: 동시 연결 제한
- minPoolSize=5: 최소 연결 유지 (Cold Start 방지)
- maxIdleTimeMS=60000: 유휴 연결 정리

================================================================================
"""

from typing import List
import logging
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from beanie import init_beanie, Document
from legacy.app.core.config import settings


# =============================================================================
# 전역 MongoDB 연결 객체 (Global MongoDB Connection Objects)
# =============================================================================
#
# 모듈 수준의 전역 변수로 관리
# - client: MongoDB 클라이언트 (커넥션 풀 포함)
# - database: 사용할 데이터베이스 인스턴스
#
# 초기값 None으로 설정하고, connect_to_mongo()에서 초기화
#
# =============================================================================

client: AsyncIOMotorClient = None
"""
MongoDB 클라이언트 인스턴스

커넥션 풀을 관리하며, 여러 데이터베이스에 접근 가능
애플리케이션 종료 시 close_mongo_connection()으로 정리
"""

database: AsyncIOMotorDatabase = None
"""
사용할 MongoDB 데이터베이스 인스턴스

client['database_name'] 또는 client.database_name으로 접근
현재는 'chat_db'로 하드코딩
"""

logger = logging.getLogger(__name__)


# =============================================================================
# Beanie 문서 모델 등록 (Beanie Document Models)
# =============================================================================
#
# init_beanie()에 전달할 문서 모델 목록
# 새 모델 추가 시 이 목록에 추가해야 함
#
# =============================================================================

# MongoDB document models import
from legacy.app.models.messages import Message
# from legacy.app.models.message_search import MessageSearch  # TODO: Elasticsearch 도입 시 활성화

DOCUMENT_MODELS: List[Document] = [
    Message,
    # MessageSearch,  # TODO: Elasticsearch 도입 시 활성화
]
"""
Beanie에 등록할 문서 모델 목록

새 Document 클래스 추가 시:
1. app/models/에 모델 파일 생성
2. 이 파일에서 import
3. DOCUMENT_MODELS 리스트에 추가
"""


# =============================================================================
# MongoDB 연결 (MongoDB Connection)
# =============================================================================

async def connect_to_mongo():
    """
    최적화된 설정으로 MongoDB 연결 생성

    =========================================================================
    AsyncIOMotorClient 주요 파라미터
    =========================================================================

    연결 풀 설정:
    - maxPoolSize: 최대 연결 수 (기본 100)
    - minPoolSize: 최소 연결 수 (기본 0)
    - maxIdleTimeMS: 유휴 연결 유지 시간
    - waitQueueTimeoutMS: 연결 대기 타임아웃

    타임아웃 설정:
    - connectTimeoutMS: 연결 수립 타임아웃
    - serverSelectionTimeoutMS: 서버 선택 타임아웃
    - socketTimeoutMS: 소켓 작업 타임아웃

    쓰기 옵션:
    - w: 쓰기 확인 레벨 ("majority", 1, 0)
    - retryWrites: 쓰기 재시도 활성화

    =========================================================================
    연결 풀 크기 결정
    =========================================================================

    maxPoolSize=20 선택 이유:
    - FastAPI 워커당 20개 연결
    - 워커 4개 = 총 80개 연결 (MongoDB 기본 제한 이내)
    - 동시 요청 수에 따라 조정

    minPoolSize=5 선택 이유:
    - Cold Start 방지 (연결 생성 지연 ~50ms)
    - 기본 부하 처리에 충분
    - 메모리 사용량과 트레이드오프

    =========================================================================
    Write Concern 설정
    =========================================================================

    w="majority":
    - 과반수 replica set 멤버에 쓰기 확인
    - 데이터 내구성 보장
    - 약간의 지연 증가

    대안:
    - w=1: 단일 노드 확인 (빠르지만 덜 안전)
    - w=0: 확인 없음 (가장 빠르지만 위험)

    =========================================================================
    압축 설정
    =========================================================================

    compressors=["zstd", "snappy", "zlib"]:
    - 네트워크 트래픽 압축
    - MongoDB 4.2+에서 지원
    - 우선순위: zstd > snappy > zlib

    압축 효과:
    - 네트워크 대역폭 절약 (30-50%)
    - CPU 사용량 약간 증가
    - 대용량 문서에서 효과적

    Raises:
        Exception: MongoDB 연결 실패

    Example:
        >>> await connect_to_mongo()
        >>> # 이제 database 변수로 DB 접근 가능
    """
    global client, database

    try:
        client = AsyncIOMotorClient(
            settings.mongo_url,

            # -----------------------------------------------------------------
            # 연결 풀 설정
            #
            # maxPoolSize: 최대 연결 수 (기본 100 → 20)
            #   - 너무 크면 MongoDB 서버 부담
            #   - 너무 작으면 연결 대기 발생
            #
            # minPoolSize: 최소 연결 수 (기본 0 → 5)
            #   - 0이면 Cold Start 시 지연
            #   - 5개 미리 연결해두면 즉시 사용 가능
            # -----------------------------------------------------------------
            maxPoolSize=20,
            minPoolSize=5,

            # -----------------------------------------------------------------
            # 유휴 연결 설정
            #
            # maxIdleTimeMS: 유휴 연결 유지 시간 (기본 없음 → 60초)
            #   - 사용되지 않는 연결 정리
            #   - 메모리 절약
            #   - minPoolSize보다 많은 연결만 해당
            # -----------------------------------------------------------------
            maxIdleTimeMS=60000,

            # -----------------------------------------------------------------
            # 대기열 타임아웃
            #
            # waitQueueTimeoutMS: 연결 대기 최대 시간 (기본 없음 → 10초)
            #   - 모든 연결이 사용 중일 때 대기
            #   - 타임아웃 시 에러 발생
            #   - 0이면 무한 대기 (위험)
            # -----------------------------------------------------------------
            waitQueueTimeoutMS=10000,

            # -----------------------------------------------------------------
            # 연결 타임아웃 설정
            #
            # connectTimeoutMS: TCP 연결 타임아웃 (기본 20초 → 10초)
            # serverSelectionTimeoutMS: 서버 선택 타임아웃 (기본 30초 → 5초)
            # socketTimeoutMS: 소켓 작업 타임아웃 (기본 없음 → 30초)
            # -----------------------------------------------------------------
            connectTimeoutMS=10000,
            serverSelectionTimeoutMS=5000,
            socketTimeoutMS=30000,

            # -----------------------------------------------------------------
            # 쓰기 옵션
            #
            # w="majority": 과반수 replica에 쓰기 확인
            #   - 프라이머리 + 1개 이상의 세컨더리에 쓰기
            #   - 데이터 손실 방지
            #
            # retryWrites=True: 일시적 오류 시 쓰기 재시도
            #   - 네트워크 오류, failover 시 자동 재시도
            #
            # retryReads=True: 일시적 오류 시 읽기 재시도
            # -----------------------------------------------------------------
            w="majority",
            retryWrites=True,
            retryReads=True,

            # -----------------------------------------------------------------
            # 압축 설정
            #
            # 네트워크 트래픽 압축으로 대역폭 절약
            # 서버와 클라이언트가 모두 지원하는 알고리즘 사용
            #
            # 우선순위:
            # 1. zstd: 최신, 가장 효율적 (MongoDB 4.2+)
            # 2. snappy: 빠름, 적당한 압축률
            # 3. zlib: 높은 압축률, 느림
            # -----------------------------------------------------------------
            compressors=["zstd", "snappy", "zlib"],
        )

        # 데이터베이스 선택
        database = client.chat_db

        logger.info("Connected to MongoDB with optimized settings")

    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise


# =============================================================================
# MongoDB + Beanie 초기화 (Initialize MongoDB with Beanie)
# =============================================================================

async def init_mongodb():
    """
    MongoDB 연결 및 Beanie ODM 초기화

    =========================================================================
    초기화 순서
    =========================================================================

    1. connect_to_mongo(): MongoDB 연결 생성
    2. init_beanie(): Beanie ODM 초기화
       - 문서 모델 등록
       - 인덱스 생성

    =========================================================================
    Beanie 초기화 상세
    =========================================================================

    init_beanie() 수행 작업:
    1. 각 Document 클래스에 대해:
       - 컬렉션 이름 결정 (Settings.name 또는 클래스명)
       - 인덱스 생성 (Settings.indexes)
    2. 문서 클래스에 database 참조 연결
    3. 유효성 검사 설정

    =========================================================================
    호출 시점
    =========================================================================

    FastAPI 애플리케이션 시작 시:
    ```python
    @app.on_event("startup")
    async def startup():
        await init_mongodb()
    ```

    Raises:
        Exception: MongoDB 연결 또는 Beanie 초기화 실패

    Example:
        >>> await init_mongodb()
        >>> # 이제 Beanie Document 모델 사용 가능
        >>> message = await Message.find_one({"room_id": 123})
    """
    try:
        # Step 1: MongoDB 연결
        await connect_to_mongo()

        # Step 2: Beanie ODM 초기화
        await init_beanie(database=database, document_models=DOCUMENT_MODELS)

        logger.info("MongoDB initialized with Beanie successfully")

    except Exception as e:
        logger.error(f"Failed to initialize MongoDB: {e}")
        raise


# =============================================================================
# MongoDB 연결 상태 확인 (Connection Health Check)
# =============================================================================

async def check_mongo_connection() -> bool:
    """
    MongoDB 연결 상태 확인

    =========================================================================
    ping 명령어 사용 이유
    =========================================================================

    admin.command('ping'):
    - 가장 가벼운 관리 명령어
    - 연결 상태만 확인
    - 데이터 접근 불필요

    =========================================================================
    사용 시나리오
    =========================================================================

    1. 헬스체크 API (/health)
    2. 애플리케이션 시작 시 연결 확인
    3. 모니터링 시스템에서 주기적 확인

    Returns:
        bool: 연결 성공 여부 (True/False)

    Example:
        >>> if await check_mongo_connection():
        ...     print("MongoDB 연결 정상")
        ... else:
        ...     print("MongoDB 연결 실패")
    """
    try:
        if client:
            await client.admin.command('ping')
            return True
        return False
    except Exception as e:
        logger.error(f"MongoDB connection check failed: {e}")
        return False


# =============================================================================
# MongoDB 연결 종료 (Connection Cleanup)
# =============================================================================

async def close_mongo_connection():
    """
    MongoDB 연결 종료

    =========================================================================
    동작 내용
    =========================================================================

    client.close():
    1. 모든 커넥션 풀 연결 닫기
    2. 백그라운드 작업 정리
    3. 리소스 해제

    =========================================================================
    호출 시점
    =========================================================================

    FastAPI 애플리케이션 종료 시:
    ```python
    @app.on_event("shutdown")
    async def shutdown():
        await close_mongo_connection()
    ```

    =========================================================================
    주의사항
    =========================================================================

    - close() 후 client 사용 불가
    - 재연결 시 connect_to_mongo() 다시 호출

    Example:
        >>> await close_mongo_connection()
    """
    global client

    if client:
        client.close()
        client = None
        logger.info("MongoDB connection closed")


# =============================================================================
# 데이터베이스 인스턴스 제공 (Database Instance Provider)
# =============================================================================

def get_database() -> AsyncIOMotorDatabase:
    """
    MongoDB 데이터베이스 인스턴스 반환

    =========================================================================
    사용 시나리오
    =========================================================================

    Beanie를 거치지 않고 직접 컬렉션 접근 필요 시:
    ```python
    db = get_database()
    result = await db.collection_name.find_one({"key": "value"})
    ```

    집계(Aggregation) 파이프라인 사용 시:
    ```python
    db = get_database()
    pipeline = [{"$match": ...}, {"$group": ...}]
    result = await db.messages.aggregate(pipeline).to_list(None)
    ```

    =========================================================================
    주의사항
    =========================================================================

    init_mongodb() 호출 전에 사용하면 에러 발생
    FastAPI 시작 이벤트 이후에만 사용

    Returns:
        AsyncIOMotorDatabase: MongoDB 데이터베이스 인스턴스

    Raises:
        RuntimeError: init_mongodb()가 호출되지 않은 경우

    Example:
        >>> db = get_database()
        >>> collections = await db.list_collection_names()
    """
    if database is None:
        raise RuntimeError("MongoDB not initialized. Call init_mongodb() first.")
    return database


# =============================================================================
# 커넥션 풀 모니터링 (Connection Pool Monitoring)
# =============================================================================

async def get_pool_status() -> dict:
    """
    MongoDB 커넥션 풀 상태 조회 (모니터링용)

    =========================================================================
    serverStatus 명령어
    =========================================================================

    MongoDB 서버 상태 정보 반환
    connections 섹션에서 연결 정보 추출

    반환 정보:
    - current: 현재 열린 연결 수
    - available: 사용 가능한 연결 수
    - totalCreated: 총 생성된 연결 수
    - active: 현재 활성 연결 수 (작업 중)

    =========================================================================
    모니터링 지표
    =========================================================================

    1. current 높음:
       - 많은 동시 요청
       - 연결 누수 가능성

    2. available 낮음:
       - maxPoolSize에 근접
       - 풀 크기 증가 고려

    3. totalCreated 빠르게 증가:
       - 연결 재사용 안 됨
       - 연결 생성/해제 오버헤드

    =========================================================================
    주의사항
    =========================================================================

    serverStatus 명령은 약간의 오버헤드 있음
    너무 자주 호출하지 않도록 주의 (10-60초 간격 권장)

    Returns:
        dict: 풀 상태 정보
            - current: 현재 연결 수
            - available: 사용 가능 연결 수
            - total_created: 총 생성된 연결 수
            - active: 활성 연결 수
            또는
            - status: "disconnected" (연결 안 됨)
            - status: "error", message: 에러 메시지

    Example:
        >>> status = await get_pool_status()
        >>> print(f"현재 연결: {status['current']}")
        >>> print(f"가용 연결: {status['available']}")
    """
    if client is None:
        return {"status": "disconnected"}

    try:
        # serverStatus 명령으로 서버 상태 조회
        server_status = await client.admin.command("serverStatus")
        connections = server_status.get("connections", {})

        return {
            "current": connections.get("current", 0),       # 현재 연결 수
            "available": connections.get("available", 0),   # 사용 가능 연결 수
            "total_created": connections.get("totalCreated", 0),  # 총 생성된 연결 수
            "active": connections.get("active", 0),         # 활성 연결 수
        }

    except Exception as e:
        logger.error(f"Failed to get MongoDB pool status: {e}")
        return {"status": "error", "message": str(e)}
