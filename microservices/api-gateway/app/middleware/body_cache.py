"""
Body Cache Middleware

요청 바디를 캐싱하여 여러 미들웨어에서 읽을 수 있도록 합니다.
"""
from starlette.types import ASGIApp, Receive, Scope, Send, Message


class BodyCacheMiddleware:
    """
    ASGI 미들웨어: 요청 바디를 캐싱

    Starlette의 BaseHTTPMiddleware는 body를 한 번만 읽을 수 있는 문제가 있어
    Pure ASGI 미들웨어로 구현하여 body를 캐싱합니다.
    """

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # body 청크를 캐싱
        body_parts: list[bytes] = []
        body_complete = False

        async def cached_receive() -> Message:
            nonlocal body_complete

            # 이미 캐싱된 body가 있으면 반환
            if body_complete and body_parts:
                return {
                    "type": "http.request",
                    "body": b"".join(body_parts),
                    "more_body": False,
                }

            # 새로운 메시지 수신
            message = await receive()

            if message["type"] == "http.request":
                body = message.get("body", b"")
                if body:
                    body_parts.append(body)

                if not message.get("more_body", False):
                    body_complete = True

                # 캐시된 전체 body를 scope에 저장
                scope["_cached_body"] = b"".join(body_parts)

            return message

        await self.app(scope, cached_receive, send)
