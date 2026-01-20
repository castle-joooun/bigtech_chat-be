import json
import logging
from datetime import datetime
from typing import Dict, Any
from fastapi import WebSocket

from app.websockets.connection_manager import manager
from app.models.messages import Message
from app.models.chat_rooms import ChatRoom

logger = logging.getLogger(__name__)


class WebSocketMessageHandler:
    """WebSocket 메시지 처리 핸들러"""
    
    @staticmethod
    async def handle_message(websocket: WebSocket, data: Dict[str, Any]):
        """
        WebSocket으로 받은 메시지를 처리합니다.
        
        Args:
            websocket: WebSocket 연결 객체
            data: 클라이언트에서 전송한 메시지 데이터
        """
        if websocket not in manager.connection_info:
            logger.error("Message received from unregistered WebSocket connection")
            return
        
        connection_info = manager.connection_info[websocket]
        user_id = connection_info["user_id"]
        room_id = connection_info["room_id"]
        
        message_type = data.get("type")
        
        if message_type == "message":
            await WebSocketMessageHandler._handle_chat_message(user_id, room_id, data)
        elif message_type == "typing":
            await WebSocketMessageHandler._handle_typing_indicator(user_id, room_id, data)
        elif message_type == "ping":
            await WebSocketMessageHandler._handle_ping(websocket, user_id)
        else:
            logger.warning(f"Unknown message type: {message_type} from user {user_id}")

    @staticmethod
    async def _handle_chat_message(user_id: str, room_id: str, data: Dict[str, Any]):
        """채팅 메시지를 처리합니다."""
        try:
            content = data.get("content", "").strip()
            if not content:
                logger.warning(f"Empty message content from user {user_id}")
                return

            # 메시지를 데이터베이스에 저장
            message = Message(
                room_id=room_id,
                sender_id=user_id,
                content=content,
                message_type=data.get("message_type", "text"),
                created_at=datetime.utcnow()
            )
            await message.insert()

            # 채팅방의 마지막 메시지 업데이트
            await ChatRoom.find_one(ChatRoom.id == room_id).update({
                "$set": {
                    "last_message": content,
                    "last_message_at": datetime.utcnow()
                }
            })

            # 새 메시지를 Redis 캐시에 추가
            try:
                from app.services.message_cache_service import cache_new_message
                message_dict = {
                    "id": str(message.id),
                    "room_id": room_id,
                    "sender_id": user_id,
                    "content": content,
                    "message_type": message.message_type,
                    "created_at": message.created_at.isoformat(),
                    "is_deleted": False
                }
                await cache_new_message(int(room_id), "private", message_dict)
            except Exception as cache_error:
                logger.warning(f"Failed to cache new message: {cache_error}")

            # 채팅방의 모든 사용자에게 메시지 브로드캐스트
            broadcast_data = {
                "type": "message",
                "message_id": str(message.id),
                "room_id": room_id,
                "sender_id": user_id,
                "content": content,
                "message_type": message.message_type,
                "created_at": message.created_at.isoformat(),
                "timestamp": datetime.utcnow().isoformat()
            }

            await manager.broadcast_to_room(room_id, broadcast_data)

            logger.info(f"Message sent from user {user_id} to room {room_id}")

        except Exception as e:
            logger.error(f"Error handling chat message from user {user_id}: {e}")
            await manager.send_personal_json({
                "type": "error",
                "message": "메시지 전송 중 오류가 발생했습니다."
            }, user_id)

    @staticmethod
    async def _handle_typing_indicator(user_id: str, room_id: str, data: Dict[str, Any]):
        """타이핑 상태 표시를 처리합니다."""
        try:
            is_typing = data.get("is_typing", False)
            
            # 채팅방의 다른 사용자들에게 타이핑 상태 브로드캐스트
            broadcast_data = {
                "type": "typing",
                "user_id": user_id,
                "room_id": room_id,
                "is_typing": is_typing,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await manager.broadcast_to_room(room_id, broadcast_data, exclude_user=user_id)
            
        except Exception as e:
            logger.error(f"Error handling typing indicator from user {user_id}: {e}")

    @staticmethod
    async def _handle_ping(websocket: WebSocket, user_id: str):
        """Ping 메시지에 대한 Pong 응답을 처리하고 활동 시간을 업데이트합니다."""
        try:
            # 사용자 활동 시간 업데이트 (heartbeat)
            from app.services.online_status_service import update_activity
            await update_activity(int(user_id))

            await websocket.send_json({
                "type": "pong",
                "timestamp": datetime.utcnow().isoformat()
            })

        except Exception as e:
            logger.error(f"Error handling ping from user {user_id}: {e}")

    @staticmethod
    async def send_system_message(room_id: str, message: str, message_type: str = "system"):
        """시스템 메시지를 채팅방에 전송합니다."""
        try:
            broadcast_data = {
                "type": "system_message",
                "room_id": room_id,
                "message": message,
                "message_type": message_type,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await manager.broadcast_to_room(room_id, broadcast_data)
            
        except Exception as e:
            logger.error(f"Error sending system message to room {room_id}: {e}")

    @staticmethod
    async def send_user_status_update(room_id: str, user_id: str, status: str):
        """사용자 상태 업데이트를 채팅방에 전송합니다."""
        try:
            online_users = manager.get_room_users(room_id)
            
            broadcast_data = {
                "type": "user_status",
                "room_id": room_id,
                "user_id": user_id,
                "status": status,
                "online_users": online_users,
                "online_count": len(online_users),
                "timestamp": datetime.utcnow().isoformat()
            }
            
            await manager.broadcast_to_room(room_id, broadcast_data)
            
        except Exception as e:
            logger.error(f"Error sending user status update to room {room_id}: {e}")


# 메시지 핸들러 인스턴스
message_handler = WebSocketMessageHandler()