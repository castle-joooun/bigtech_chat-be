from typing import Dict, Set, List
from fastapi import WebSocket
import json
import logging

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self):
        # 채팅방별 연결 그룹: {room_id: {user_id: websocket}}
        self.room_connections: Dict[str, Dict[str, WebSocket]] = {}
        # 사용자별 연결: {user_id: websocket}
        self.user_connections: Dict[str, WebSocket] = {}
        # WebSocket별 사용자 정보: {websocket: {"user_id": str, "room_id": str}}
        self.connection_info: Dict[WebSocket, Dict[str, str]] = {}

    async def connect(self, websocket: WebSocket, user_id: str, room_id: str):
        """새로운 WebSocket 연결을 등록합니다."""
        await websocket.accept()

        # 기존 연결이 있다면 제거
        if user_id in self.user_connections:
            await self.disconnect_user(user_id)

        # 새 연결 등록
        self.user_connections[user_id] = websocket

        # 채팅방별 연결 그룹에 추가
        if room_id not in self.room_connections:
            self.room_connections[room_id] = {}
        self.room_connections[room_id][user_id] = websocket

        # 연결 정보 저장
        self.connection_info[websocket] = {"user_id": user_id, "room_id": room_id}

        logger.info(f"User {user_id} connected to room {room_id}")

        # 사용자 온라인 상태 업데이트
        await self._update_user_online_status(user_id, True)

        # 채팅방에 사용자 입장 알림
        await self.broadcast_to_room(room_id, {
            "type": "user_joined",
            "user_id": user_id,
            "message": f"{user_id}님이 입장했습니다.",
            "online_users": self.get_room_users(room_id),
            "online_count": self.get_user_count_in_room(room_id)
        }, exclude_user=user_id)

    async def disconnect(self, websocket: WebSocket):
        """WebSocket 연결을 해제합니다."""
        if websocket not in self.connection_info:
            return

        connection_info = self.connection_info[websocket]
        user_id = connection_info["user_id"]
        room_id = connection_info["room_id"]

        await self._remove_connection(websocket, user_id, room_id)

        logger.info(f"User {user_id} disconnected from room {room_id}")

        # 사용자 오프라인 상태 업데이트
        await self._update_user_online_status(user_id, False)

        # 채팅방에 사용자 퇴장 알림
        await self.broadcast_to_room(room_id, {
            "type": "user_left",
            "user_id": user_id,
            "message": f"{user_id}님이 퇴장했습니다.",
            "online_users": self.get_room_users(room_id),
            "online_count": self.get_user_count_in_room(room_id)
        })

    async def disconnect_user(self, user_id: str):
        """특정 사용자의 연결을 해제합니다."""
        if user_id not in self.user_connections:
            return
        
        websocket = self.user_connections[user_id]
        if websocket in self.connection_info:
            room_id = self.connection_info[websocket]["room_id"]
            await self._remove_connection(websocket, user_id, room_id)
            
            try:
                await websocket.close()
            except Exception:
                pass

    async def _remove_connection(self, websocket: WebSocket, user_id: str, room_id: str):
        """연결 정보를 제거합니다."""
        # 사용자 연결에서 제거
        if user_id in self.user_connections:
            del self.user_connections[user_id]
        
        # 채팅방 연결에서 제거
        if room_id in self.room_connections:
            if user_id in self.room_connections[room_id]:
                del self.room_connections[room_id][user_id]
            
            # 채팅방에 사용자가 없으면 방 자체를 제거
            if not self.room_connections[room_id]:
                del self.room_connections[room_id]
        
        # 연결 정보에서 제거
        if websocket in self.connection_info:
            del self.connection_info[websocket]

    async def send_personal_message(self, message: str, user_id: str):
        """특정 사용자에게 메시지를 전송합니다."""
        if user_id in self.user_connections:
            websocket = self.user_connections[user_id]
            try:
                await websocket.send_text(message)
            except Exception as e:
                logger.error(f"Failed to send message to user {user_id}: {e}")
                await self.disconnect_user(user_id)

    async def send_personal_json(self, data: dict, user_id: str):
        """특정 사용자에게 JSON 데이터를 전송합니다."""
        if user_id in self.user_connections:
            websocket = self.user_connections[user_id]
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.error(f"Failed to send JSON to user {user_id}: {e}")
                await self.disconnect_user(user_id)

    async def broadcast_to_room(self, room_id: str, data: dict, exclude_user: str = None):
        """채팅방의 모든 사용자에게 메시지를 브로드캐스트합니다."""
        if room_id not in self.room_connections:
            return
        
        disconnected_users = []
        
        for user_id, websocket in self.room_connections[room_id].items():
            if exclude_user and user_id == exclude_user:
                continue
            
            try:
                await websocket.send_json(data)
            except Exception as e:
                logger.error(f"Failed to send message to user {user_id} in room {room_id}: {e}")
                disconnected_users.append(user_id)
        
        # 연결이 끊어진 사용자들 정리
        for user_id in disconnected_users:
            await self.disconnect_user(user_id)

    def get_room_users(self, room_id: str) -> List[str]:
        """채팅방에 연결된 사용자 목록을 반환합니다."""
        if room_id not in self.room_connections:
            return []
        return list(self.room_connections[room_id].keys())

    def get_user_count_in_room(self, room_id: str) -> int:
        """채팅방의 연결된 사용자 수를 반환합니다."""
        if room_id not in self.room_connections:
            return 0
        return len(self.room_connections[room_id])

    def is_user_connected(self, user_id: str) -> bool:
        """사용자가 연결되어 있는지 확인합니다."""
        return user_id in self.user_connections

    def get_user_room(self, user_id: str) -> str:
        """사용자가 연결된 채팅방 ID를 반환합니다."""
        if user_id not in self.user_connections:
            return None

        websocket = self.user_connections[user_id]
        if websocket in self.connection_info:
            return self.connection_info[websocket]["room_id"]
        return None

    async def _update_user_online_status(self, user_id: str, is_online: bool):
        """사용자의 온라인 상태를 Redis에 업데이트합니다."""
        try:
            from app.services.online_status_service import set_online, set_offline

            user_id_int = int(user_id)

            if is_online:
                # WebSocket 연결 시 온라인 상태로 설정
                websocket_session_id = f"ws_{user_id}_{id(self)}"  # 고유한 세션 ID 생성
                success = await set_online(user_id_int, session_id=websocket_session_id)
                if success:
                    logger.info(f"User {user_id} set to online via WebSocket")
                else:
                    logger.warning(f"Failed to set user {user_id} online via WebSocket")
            else:
                # WebSocket 연결 해제 시 오프라인 상태로 설정
                success = await set_offline(user_id_int)
                if success:
                    logger.info(f"User {user_id} set to offline via WebSocket")
                else:
                    logger.warning(f"Failed to set user {user_id} offline via WebSocket")

        except Exception as e:
            logger.error(f"Error in _update_user_online_status: {e}")

    async def broadcast_user_status_update(self, user_id: str, is_online: bool):
        """사용자 상태 변경을 모든 관련 사용자에게 브로드캐스트합니다."""
        try:
            # 해당 사용자와 관련된 모든 채팅방에 상태 업데이트 브로드캐스트
            status_data = {
                "type": "user_status_update",
                "user_id": user_id,
                "is_online": is_online,
                "timestamp": str(self._get_current_timestamp())
            }

            # 현재 연결된 모든 방에 브로드캐스트
            # TODO: 실제로는 해당 사용자와 친구 관계이거나 공통 채팅방에 있는 사용자들에게만 전송해야 함
            for room_id in self.room_connections:
                await self.broadcast_to_room(room_id, status_data)

        except Exception as e:
            logger.error(f"Error broadcasting user status update: {e}")

    def _get_current_timestamp(self):
        """현재 타임스탬프를 반환합니다."""
        from datetime import datetime
        return datetime.utcnow()

    def get_online_users(self) -> List[str]:
        """현재 온라인인 모든 사용자 목록을 반환합니다."""
        return list(self.user_connections.keys())

    def get_online_users_count(self) -> int:
        """현재 온라인인 사용자 수를 반환합니다."""
        return len(self.user_connections)


# 전역 연결 매니저 인스턴스
manager = ConnectionManager()