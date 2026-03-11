"""
Authentication API Endpoints (인증 API 엔드포인트)
==================================================

사용자 인증(회원가입, 로그인, 로그아웃)을 처리하는 API 레이어입니다.

아키텍처 개요
-------------
```
┌─────────────────────────────────────────────────────────┐
│  API Layer (현재 파일)                                    │
│  ┌─────────────────────────────────────────────────┐   │
│  │ - HTTP 요청/응답 처리                            │   │
│  │ - 입력 검증 (Pydantic, Validator)               │   │
│  │ - 인증/인가 (OAuth2, JWT)                       │   │
│  │ - 응답 직렬화                                   │   │
│  └───────────────────────┬─────────────────────────┘   │
└──────────────────────────┼─────────────────────────────┘
                           │ Depends(get_async_session)
                           │ Depends(get_current_user)
                           ▼
┌─────────────────────────────────────────────────────────┐
│  Service Layer (auth_service.py)                         │
│  - 데이터베이스 작업                                      │
│  - 비즈니스 로직                                          │
└─────────────────────────────────────────────────────────┘
```

엔드포인트 목록
---------------
| Method | Path           | 설명              | 인증 |
|--------|----------------|-------------------|------|
| POST   | /auth/register | 회원가입          | X    |
| POST   | /auth/login    | 로그인 (OAuth2)   | X    |
| POST   | /auth/login/json| 로그인 (JSON)    | X    |
| POST   | /auth/logout   | 로그아웃          | O    |

설계 패턴
---------
1. Dependency Injection (의존성 주입):
   - Depends(get_async_session): DB 세션 주입
   - Depends(get_current_user): 인증된 사용자 주입

2. OAuth2 + JWT:
   - OAuth2PasswordBearer: 표준 OAuth2 인증 스킴
   - JWT: 토큰 기반 무상태(Stateless) 인증

3. Layered Architecture:
   - API 레이어는 HTTP만 담당
   - 비즈니스 로직은 Service 레이어에 위임

SOLID 원칙
----------
- SRP: 인증 관련 엔드포인트만 담당
- OCP: 새 인증 방식 추가 시 새 엔드포인트 추가
- DIP: auth_service 추상화에 의존

보안 고려사항
-------------
1. 비밀번호:
   - bcrypt로 해싱 (salt 자동 생성)
   - 비동기 처리로 이벤트 루프 블로킹 방지

2. JWT:
   - 만료 시간 설정 (settings.access_token_expire_hours)
   - HTTPS 전용 (프로덕션)

3. 입력 검증:
   - Pydantic 스키마로 타입 검증
   - Validator로 비즈니스 규칙 검증

이벤트 발행
-----------
- UserRegistered: 회원가입 완료 시
- UserOnlineStatusChanged: 로그인/로그아웃 시

관련 파일
---------
- app/services/auth_service.py: 비즈니스 로직
- app/schemas/user.py: 요청/응답 스키마
- app/kafka/events.py: 도메인 이벤트
- app/utils/auth.py: JWT 및 비밀번호 유틸리티
"""

from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.config import settings
from app.database.mysql import get_async_session
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserResponse, Token, TokenData
from app.utils.auth import (
    verify_password,
    get_password_hash,
    get_password_hash_async,
    create_access_token,
    decode_access_token
)
from shared_lib.core import (
    user_not_found_error,
    invalid_credentials_error,
    email_already_exists_error,
    username_already_exists_error,
    invalid_token_error,
    AuthenticationException
)
from shared_lib.core import validate_user_registration, validate_user_login
from app.services import auth_service
from app.services.online_status_service import set_online, set_offline, update_activity
from app.kafka.producer import get_event_producer
from app.kafka.events import UserRegistered, UserOnlineStatusChanged

# Gateway 기반 인증 의존성 import
from app.api.dependencies import get_current_user, get_optional_user


# =============================================================================
# OAuth2 설정 (Swagger UI 전용)
# =============================================================================

# OAuth2PasswordBearer: Swagger UI 인증용
# - 실제 인증은 Gateway에서 처리
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

# APIRouter: 관련 엔드포인트 그룹화
router = APIRouter(prefix="/api/auth", tags=["Authentication"])


# =============================================================================
# API Endpoints
# =============================================================================

@router.post("/register",
             response_model=UserResponse,
             status_code=status.HTTP_201_CREATED)
async def register(
        user_data: UserCreate,
        db: AsyncSession = Depends(get_async_session)
) -> UserResponse:
    """
    사용자 회원가입

    플로우:
        1. 입력 검증 (이메일 형식, 비밀번호 규칙 등)
        2. 이메일 중복 확인
        3. 사용자명 중복 확인
        4. 비밀번호 해싱 (bcrypt, 비동기)
        5. 사용자 생성
        6. Kafka 이벤트 발행 (UserRegistered)

    Args:
        user_data: 회원가입 요청 데이터
            - email: 이메일 주소 (유니크)
            - username: 사용자명 (유니크, 영문/숫자/밑줄)
            - password: 비밀번호 (8-16자, 영문+숫자+특수문자)
            - display_name: 표시 이름 (선택)
        db: SQLAlchemy 비동기 세션

    Returns:
        UserResponse: 생성된 사용자 정보

    Raises:
        HTTPException 400: 입력 검증 실패
        HTTPException 409: 이메일 또는 사용자명 중복

    Kafka Event:
        Topic: user.events
        Event: UserRegistered
            - user_id: 생성된 사용자 ID
            - email, username, display_name
            - timestamp
    """
    # 1. 입력 검증 (이메일 형식, 비밀번호 규칙)
    validate_user_registration(
        user_data.email,
        user_data.username,
        user_data.password
    )

    # 2. 이메일 중복 확인
    if await auth_service.is_email_exists(db, user_data.email):
        raise email_already_exists_error()

    # 3. 사용자명 중복 확인
    if await auth_service.is_username_exists(db, user_data.username):
        raise username_already_exists_error()

    # 4. 비밀번호 해싱 (비동기 처리)
    # - bcrypt는 CPU 집약적이므로 ThreadPoolExecutor 사용
    # - 이벤트 루프 블로킹 방지
    password_hash = await get_password_hash_async(user_data.password)

    # 5. 사용자 생성
    user = await auth_service.create_user(
        db=db,
        email=user_data.email,
        username=user_data.username,
        password_hash=password_hash,
        display_name=user_data.display_name
    )

    # 6. Kafka 이벤트 발행
    # - Friend Service 등 다른 서비스에서 구독
    producer = get_event_producer()
    await producer.publish(
        topic=settings.kafka_topic_user_events,
        event=UserRegistered(
            user_id=user.id,
            email=user.email,
            username=user.username,
            display_name=user.display_name or user.username,
            timestamp=datetime.utcnow()
        ),
        key=str(user.id)  # 파티션 키로 user_id 사용 → 순서 보장
    )

    return user


@router.post("/login", response_model=Token)
async def login_oauth2(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: AsyncSession = Depends(get_async_session)
) -> Token:
    """
    사용자 로그인 (OAuth2 표준)

    Swagger UI 전용:
        - Swagger의 "Authorize" 버튼에서 사용
        - application/x-www-form-urlencoded 형식
        - username 필드에 이메일 입력 (OAuth2 표준)

    플로우:
        1. 입력 검증
        2. 이메일/비밀번호로 사용자 인증
        3. JWT 액세스 토큰 생성
        4. Redis에 온라인 상태 저장
        5. MySQL에 온라인 상태 업데이트
        6. Kafka 이벤트 발행 (UserOnlineStatusChanged)

    Args:
        form_data: OAuth2 폼 데이터
            - username: 이메일 주소 (OAuth2 표준)
            - password: 비밀번호
        db: SQLAlchemy 비동기 세션

    Returns:
        Token: JWT 액세스 토큰
            - access_token: JWT 토큰 문자열
            - token_type: "bearer"
            - expires_in: 만료 시간 (초)

    Raises:
        HTTPException 401: 인증 실패

    Kafka Event:
        Topic: user.online_status
        Event: UserOnlineStatusChanged
            - user_id
            - is_online: True
            - timestamp
    """
    # OAuth2PasswordRequestForm의 username 필드를 email로 사용
    email = form_data.username
    password = form_data.password

    # 입력 검증
    validate_user_login(email, password)

    # 사용자 인증 (이메일 + 비밀번호)
    user = await auth_service.authenticate_user_by_email(
        db,
        email,
        password
    )
    if not user:
        raise invalid_credentials_error()

    # 액세스 토큰 생성
    access_token_expires = timedelta(hours=settings.access_token_expire_hours)
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=access_token_expires
    )

    # Redis에 온라인 상태 저장 (TTL 1시간)
    await set_online(user.id,
                     session_id=f"login_{user.id}_{access_token[:10]}")

    # MySQL DB에도 온라인 상태 업데이트
    await auth_service.update_online_status(db, user.id, is_online=True)

    # Kafka 이벤트 발행 (온라인 상태)
    producer = get_event_producer()
    await producer.publish(
        topic=settings.kafka_topic_user_online_status,
        event=UserOnlineStatusChanged(
            user_id=user.id,
            is_online=True,
            timestamp=datetime.utcnow()
        ),
        key=str(user.id)
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=int(access_token_expires.total_seconds())
    )


@router.post("/login/json", response_model=Token)
async def login_json(
        user_data: UserLogin,
        db: AsyncSession = Depends(get_async_session)
) -> Token:
    """
    사용자 로그인 (JSON 형식)

    클라이언트 앱 전용:
        - JSON 형식 (application/json)
        - email과 password 필드 사용
        - 일반 클라이언트 앱에서 사용

    Args:
        user_data: 로그인 요청 데이터
            - email: 이메일 주소
            - password: 비밀번호
        db: SQLAlchemy 비동기 세션

    Returns:
        Token: JWT 액세스 토큰

    Raises:
        HTTPException 401: 인증 실패
    """
    # 입력 검증
    validate_user_login(user_data.email, user_data.password)

    # 사용자 인증
    user = await auth_service.authenticate_user_by_email(
        db,
        user_data.email,
        user_data.password
    )
    if not user:
        raise invalid_credentials_error()

    # 액세스 토큰 생성
    access_token_expires = timedelta(hours=settings.access_token_expire_hours)
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email},
        expires_delta=access_token_expires
    )

    # Redis에 온라인 상태 저장
    await set_online(user.id,
                     session_id=f"login_{user.id}_{access_token[:10]}")

    # MySQL DB에도 온라인 상태 업데이트
    await auth_service.update_online_status(db, user.id, is_online=True)

    # Kafka 이벤트 발행 (온라인 상태)
    producer = get_event_producer()
    await producer.publish(
        topic=settings.kafka_topic_user_online_status,
        event=UserOnlineStatusChanged(
            user_id=user.id,
            is_online=True,
            timestamp=datetime.utcnow()
        ),
        key=str(user.id)
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=int(access_token_expires.total_seconds())
    )


@router.post("/logout")
async def logout(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_async_session)
) -> dict:
    """
    사용자 로그아웃

    인증 필수:
        - Authorization: Bearer {token} 헤더 필요
        - get_current_user 디펜던시로 인증 확인

    플로우:
        1. Redis에서 온라인 상태 제거
        2. MySQL에 오프라인 상태 + last_seen_at 업데이트
        3. Kafka 이벤트 발행 (UserOnlineStatusChanged)

    Args:
        current_user: 현재 인증된 사용자 (Depends로 주입)
        db: SQLAlchemy 비동기 세션

    Returns:
        dict: 로그아웃 성공 메시지
            - message: "Successfully logged out"
            - user_id: 로그아웃한 사용자 ID

    Kafka Event:
        Topic: user.online_status
        Event: UserOnlineStatusChanged
            - user_id
            - is_online: False
            - timestamp
    """
    # Redis에서 온라인 상태 제거
    await set_offline(current_user.id)

    # MySQL DB에도 오프라인 상태 및 마지막 접속 시간 업데이트
    await auth_service.update_online_status(db, current_user.id, is_online=False)

    # Kafka 이벤트 발행 (오프라인 상태)
    producer = get_event_producer()
    await producer.publish(
        topic=settings.kafka_topic_user_online_status,
        event=UserOnlineStatusChanged(
            user_id=current_user.id,
            is_online=False,
            timestamp=datetime.utcnow()
        ),
        key=str(current_user.id)
    )

    return {
        "message": "Successfully logged out",
        "user_id": current_user.id
    }
