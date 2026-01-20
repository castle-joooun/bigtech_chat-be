import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, status, Depends
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.websockets.connection_manager import manager
from app.websockets.auth import authenticate_websocket, verify_room_access
from app.websockets.handlers import message_handler
from app.api.auth import get_current_user
from app.models.users import User
from app.models.room_members import RoomMember
from app.database.mysql import get_async_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])


@router.websocket("/chat/{room_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    room_id: str,
):
    """
    채팅방 WebSocket 연결 엔드포인트
    
    Args:
        websocket: WebSocket 연결 객체
        room_id: 채팅방 ID
        token: JWT 액세스 토큰
    """
    token = websocket.headers.get('Authorization')

    # 1. WebSocket 인증
    user_id = await authenticate_websocket(websocket, token)
    if not user_id:
        return
    
    # 2. 채팅방 접근 권한 확인
    has_access = await verify_room_access(user_id, room_id)
    if not has_access:
        logger.warning(f"User {user_id} denied access to room {room_id}")
        await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
        return
    
    # 3. 연결 등록
    try:
        await manager.connect(websocket, user_id, room_id)
        
        # 4. 사용자 상태 업데이트 전송
        await message_handler.send_user_status_update(room_id, user_id, "online")
        
        # 5. 연결 환영 메시지
        await websocket.send_json({
            "type": "connection_established",
            "message": "채팅방에 연결되었습니다.",
            "room_id": room_id,
            "user_id": user_id,
            "online_users": manager.get_room_users(room_id),
            "online_count": manager.get_user_count_in_room(room_id)
        })
        
        # 6. 메시지 수신 루프
        while True:
            try:
                # 클라이언트로부터 메시지 수신
                data = await websocket.receive_json()
                
                # 메시지 처리
                await message_handler.handle_message(websocket, data)
                
            except ValueError as e:
                # JSON 파싱 오류
                logger.error(f"Invalid JSON from user {user_id}: {e}")
                try:
                    await websocket.send_json({
                        "type": "error",
                        "error_code": "invalid_json",
                        "message": "잘못된 메시지 형식입니다.",
                        "details": "JSON 형식이 올바르지 않습니다."
                    })
                except:
                    # 연결이 끊어진 경우 무시
                    break
            except ConnectionError as e:
                # 연결 오류
                logger.warning(f"Connection error for user {user_id}: {e}")
                break
            except TimeoutError as e:
                # 타임아웃 오류
                logger.warning(f"Timeout error for user {user_id}: {e}")
                try:
                    await websocket.send_json({
                        "type": "error",
                        "error_code": "timeout",
                        "message": "요청 시간이 초과되었습니다."
                    })
                except:
                    break
            except Exception as e:
                logger.error(f"Error processing message from user {user_id}: {e}")
                try:
                    await websocket.send_json({
                        "type": "error",
                        "error_code": "processing_error",
                        "message": "메시지 처리 중 오류가 발생했습니다.",
                        "details": "서버에서 메시지를 처리하는 중 문제가 발생했습니다."
                    })
                except:
                    # 연결이 끊어진 경우 루프 종료
                    break
                
    except WebSocketDisconnect:
        # 정상적인 연결 해제
        logger.info(f"WebSocket disconnected for user {user_id} in room {room_id}")
        
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket connection for user {user_id}: {e}")
        
    finally:
        # 7. 연결 해제 처리
        await manager.disconnect(websocket)
        
        # 8. 사용자 상태 업데이트 전송
        if manager.get_user_count_in_room(room_id) > 0:
            await message_handler.send_user_status_update(room_id, user_id, "offline")


@router.get("/rooms/{room_id}/status")
async def get_room_status(
    room_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    채팅방의 현재 상태 정보를 조회합니다.
    인증된 사용자이고 해당 채팅방의 멤버여야 접근 가능합니다.
    
    Args:
        room_id: 채팅방 ID
        current_user: 현재 인증된 사용자
        db: 데이터베이스 세션
        
    Returns:
        dict: 채팅방 상태 정보
    """
    try:
        # 채팅방 멤버 권한 확인
        from sqlalchemy import select
        query = select(RoomMember).where(
            RoomMember.user_id == current_user.id,
            RoomMember.chat_room_id == int(room_id)
        )
        result = await db.execute(query)
        member = result.scalar_one_or_none()
        
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="해당 채팅방에 접근할 권한이 없습니다."
            )
        
        # 채팅방 상태 정보 조회
        online_users = manager.get_room_users(room_id)
        online_count = manager.get_user_count_in_room(room_id)
        
        return {
            "room_id": room_id,
            "online_users": online_users,
            "online_count": online_count,
            "is_active": online_count > 0,
            "user_id": str(current_user.id)
        }
        
    except HTTPException:
        # 이미 처리된 HTTP 예외는 다시 발생
        raise
    except Exception as e:
        logger.error(f"Error getting room status for {room_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="채팅방 상태 조회 중 오류가 발생했습니다."
        )


