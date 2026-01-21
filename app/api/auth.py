from datetime import timedelta
from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from app.core.config import settings
from app.database.mysql import get_async_session
from app.models.users import User
from app.schemas.user import UserCreate, UserLogin, UserResponse, Token, \
    TokenData
from app.utils.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token
)
from app.core.errors import (
    user_not_found_error,
    invalid_credentials_error,
    email_already_exists_error,
    username_already_exists_error,
    invalid_token_error,
    AuthenticationException
)
from app.core.validators import validate_user_registration, validate_user_login
from app.services import auth_service
from app.services.online_status_service import set_online, set_offline, \
    update_activity

# OAuth2 설정
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
router = APIRouter(prefix="/auth", tags=["Authentication"])


async def get_current_user(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_async_session)
) -> User:
    """
    현재 인증된 사용자 조회 (단순화된 MVP 버전)
    """

    # 토큰 검증
    payload = decode_access_token(token)
    if not payload:
        raise invalid_token_error()

    # 사용자 조회
    user_id = payload.get("sub")
    if not user_id:
        raise invalid_token_error()

    user = await auth_service.find_user_by_id(db, int(user_id))
    if not user:
        raise user_not_found_error(user_id)

    # 사용자 활동 시간 업데이트 (heartbeat)
    await update_activity(user.id)

    return user


async def get_optional_user(
        token: str = Depends(oauth2_scheme),
        db: AsyncSession = Depends(get_async_session)
) -> Optional[User]:
    """
    선택적 사용자 인증 (토큰이 유효하지 않아도 None 반환)
    """
    try:
        return await get_current_user(token, db)
    except:
        return None


@router.post("/register",
             response_model=UserResponse,
             status_code=status.HTTP_201_CREATED)
async def register(
        user_data: UserCreate,
        db: AsyncSession = Depends(get_async_session)
) -> UserResponse:
    """
    사용자 회원가입 (단순화된 MVP 버전)
    """

    # 입력 검증
    validate_user_registration(
        user_data.email,
        user_data.username,
        user_data.password
    )

    # 비즈니스 로직: 이메일 중복 확인
    if await auth_service.is_email_exists(db, user_data.email):
        raise email_already_exists_error()

    # 비즈니스 로직: 사용자명 중복 확인
    if await auth_service.is_username_exists(db, user_data.username):
        raise username_already_exists_error()

    # 비밀번호 해싱 및 사용자 생성
    password_hash = get_password_hash(user_data.password)
    user = await auth_service.create_user(
        db=db,
        email=user_data.email,
        username=user_data.username,
        password_hash=password_hash,
        display_name=user_data.display_name
    )

    return user


@router.post("/login", response_model=Token)
async def login_oauth2(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: AsyncSession = Depends(get_async_session)
) -> Token:
    """
    사용자 로그인 (OAuth2 표준, Swagger UI용)

    - Swagger UI의 "Authorize" 버튼 전용
    - application/x-www-form-urlencoded 형식
    - username 필드에 email 입력
    """

    # OAuth2PasswordRequestForm의 username 필드를 email로 사용
    email = form_data.username
    password = form_data.password

    # 입력 검증
    validate_user_login(email, password)

    # 사용자 인증
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

    # Redis에 온라인 상태 저장
    await set_online(user.id,
                     session_id=f"login_{user.id}_{access_token[:10]}")

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
    사용자 로그인 (JSON 형식, 클라이언트 앱용)

    - JSON 형식 (application/json)
    - email과 password 필드 사용
    - 일반 클라이언트 앱에서 사용
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

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=int(access_token_expires.total_seconds())
    )


@router.post("/logout")
async def logout(
        current_user: User = Depends(get_current_user)
) -> dict:
    """
    사용자 로그아웃
    """
    # Redis에서 온라인 상태 제거
    await set_offline(current_user.id)

    return {
        "message": "Successfully logged out",
        "user_id": current_user.id
    }
