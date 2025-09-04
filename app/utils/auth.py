import os
import re
from datetime import datetime, timedelta
from typing import Annotated, Optional

from fastapi import Depends, HTTPException, status, Header, Request
from jose import JWTError, jwt
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext

# from app.models.user import User
# from app.services import user as user_service

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    return pwd_context.hash(password)


def password_validator(password: str):
    special_symbols = r'!"#$%&\'()*+-/:;<=>?@[₩]^_`{|}~'
    escaped_symbols = re.escape(special_symbols)

    pattern = re.compile(
        rf'^(?=.*[a-zA-Z])'  # 영문자 1개 이상
        rf'(?=.*\d)'  # 숫자 1개 이상
        rf'(?=.*[{escaped_symbols}])'  # 특수문자 1개 이상
        rf'[a-zA-Z\d{escaped_symbols}]{{8,16}}$'  # 전체 구성
    )

    if not re.match(pattern, password):
        raise HTTPException(status_code=400, detail='Invalid password')
    return get_password_hash(password)


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = (datetime.utcnow() +
                  timedelta(minutes=60*int(os.getenv('ACCESS_TOKEN_EXPIRE_HOURS'))))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, os.getenv('SECRET_KEY'), algorithm=os.getenv('ALGORITHM'))
    return encoded_jwt


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> Optional[User]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        if token is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Dose not have token",
            )

        payload = jwt.decode(token, os.getenv('SECRET_KEY'), algorithms=[os.getenv('ALGORITHM')])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        user = await user_service.get_user_item(username)
    except JWTError:
        raise credentials_exception

    return user


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)]
):

    return current_user


async def get_optional_user(request: Request) -> Optional[User]:
    print(request.headers)
    auth_header: str = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        print("[DEBUG] Authorization header 없음 또는 형식 이상:", auth_header)
        return None

    token = auth_header.removeprefix("Bearer ").strip()
    print("[DEBUG] 추출된 토큰:", token)

    try:
        payload = jwt.decode(token, os.getenv('SECRET_KEY'), algorithms=[os.getenv('ALGORITHM')])
        print("[DEBUG] 디코딩된 payload:", payload)
        username: str = payload.get("sub")
        if not username:
            print("[DEBUG] payload에 'sub' 없음")
            return None

        user = await user_service.get_user_item(username)
        if not user:
            print("[DEBUG] user_service.get_user_item 결과 없음")
        return user
    except JWTError as e:
        print("[DEBUG] JWT 디코딩 실패:", str(e))
        return None


async def get_optional_user_from_token(token: Optional[str]) -> Optional[User]:
    if not token:
        return None
    try:
        payload = jwt.decode(token, os.getenv('SECRET_KEY'), algorithms=[os.getenv('ALGORITHM')])
        username = payload.get("sub")
        if not username:
            return None
        return await user_service.get_user_item(username)
    except JWTError:
        return None

