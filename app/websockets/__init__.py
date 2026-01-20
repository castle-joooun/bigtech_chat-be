"""
WebSocket 실시간 채팅 모듈

이 모듈은 FastAPI WebSocket을 사용하여 실시간 채팅 기능을 제공합니다.

주요 구성 요소:
- connection_manager: WebSocket 연결 관리
- auth: WebSocket 인증 처리
- handlers: 메시지 처리 핸들러
"""

from .connection_manager import manager, ConnectionManager
from .auth import authenticate_websocket, verify_room_access
from .handlers import message_handler, WebSocketMessageHandler

__all__ = [
    "manager",
    "ConnectionManager",
    "authenticate_websocket",
    "verify_room_access",
    "message_handler",
    "WebSocketMessageHandler"
]