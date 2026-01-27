"""
온라인 상태 자동 업데이트 미들웨어

모든 인증된 API 요청에서 자동으로 사용자의 온라인 상태를 업데이트합니다.
이를 통해 클라이언트에서 명시적인 heartbeat 요청을 보낼 필요가 없습니다.
"""

import asyncio
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.services.online_status_service import OnlineStatusService
from app.core.logging import get_logger

logger = get_logger(__name__)


class OnlineStatusMiddleware(BaseHTTPMiddleware):
    """
    인증된 사용자의 온라인 상태를 자동으로 업데이트하는 미들웨어

    모든 API 요청 시 request.state.user가 존재하면 (인증된 요청)
    자동으로 해당 사용자의 활동을 Redis에 업데이트합니다.
    """

    async def dispatch(self, request: Request, call_next):
        # 요청 처리
        response: Response = await call_next(request)

        # 응답 후 비동기로 온라인 상태 업데이트 (응답 지연 방지)
        # request.state.user는 get_current_user()에 의해 설정됨
        if hasattr(request.state, 'user') and request.state.user:
            user_id = request.state.user.id

            # 백그라운드에서 비동기 실행 (응답에 영향 없음)
            asyncio.create_task(self._update_user_activity(user_id, request.url.path))

        return response

    async def _update_user_activity(self, user_id: int, path: str):
        """
        사용자 활동 업데이트 (백그라운드 태스크)

        Args:
            user_id: 사용자 ID
            path: API 경로 (로깅용)
        """
        try:
            # Redis에 온라인 상태 업데이트
            await OnlineStatusService.update_user_activity(user_id)

            logger.debug(f"User {user_id} activity updated via {path}")

        except Exception as e:
            # Redis 에러가 발생해도 API 응답에는 영향 없음
            logger.error(f"Failed to update user {user_id} activity: {e}")
