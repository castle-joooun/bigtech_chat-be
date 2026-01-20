from typing import Optional
from fastapi import WebSocket, status
from app.utils.auth import decode_access_token
import logging

logger = logging.getLogger(__name__)


async def authenticate_websocket(websocket: WebSocket, token: str) -> Optional[str]:
    """
    WebSocket 연결에서 JWT 토큰을 검증하고 사용자 ID를 반환합니다.
    
    Args:
        websocket: WebSocket 연결 객체
        token: Authorization 헤더에서 추출한 JWT 액세스 토큰
    
    Returns:
        str: 인증된 사용자 ID, 인증 실패 시 None
    """
    try:
        # Authorization 헤더가 없거나 Bearer 형식이 아닌 경우
        if not token:
            logger.warning("No Authorization header provided for WebSocket connection")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return None
        
        # Bearer 토큰 형식 확인 및 추출
        if not token.startswith("Bearer "):
            logger.warning("Invalid Authorization header format for WebSocket connection")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return None
        
        # Bearer 접두사 제거
        actual_token = token.replace("Bearer ", "")
        
        # JWT 토큰 디코드
        payload = decode_access_token(actual_token)
        if not payload:
            logger.warning("Invalid token provided for WebSocket connection")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("Token missing user ID (sub) for WebSocket connection")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return None
        
        logger.info(f"WebSocket authentication successful for user: {user_id}")
        return user_id
        
    except Exception as e:
        logger.error(f"WebSocket authentication error: {e}")
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        return None


async def verify_room_access(user_id: str, room_id: str) -> bool:
    """
    사용자가 특정 채팅방에 접근할 권한이 있는지 확인합니다.
    
    Args:
        user_id: 사용자 ID
        room_id: 채팅방 ID
    
    Returns:
        bool: 접근 권한이 있으면 True, 없으면 False
    """
    try:
        from app.models.room_members import RoomMember
        from app.database.mysql import get_async_session
        from sqlalchemy import select
        
        # 데이터베이스 세션 생성
        async for db in get_async_session():
            try:
                # 채팅방 멤버 확인
                query = select(RoomMember).where(
                    RoomMember.user_id == int(user_id),
                    RoomMember.chat_room_id == int(room_id)
                )
                result = await db.execute(query)
                member = result.scalar_one_or_none()
                
                return member is not None
                
            except Exception as e:
                logger.error(f"Error verifying room access for user {user_id} in room {room_id}: {e}")
                return False
            finally:
                await db.close()
                
    except Exception as e:
        logger.error(f"Database connection error in verify_room_access: {e}")
        return False