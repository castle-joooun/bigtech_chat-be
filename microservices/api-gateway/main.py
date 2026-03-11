"""
=============================================================================
FastAPI API Gateway - 메인 엔트리포인트
=============================================================================

📌 이 파일이 하는 일:
    API Gateway는 모든 클라이언트 요청의 "입구"입니다.
    마치 회사 건물의 안내 데스크처럼, 요청이 어디로 가야 하는지 결정합니다.

🔄 요청 흐름:
    클라이언트 → API Gateway → 적절한 마이크로서비스

    예시:
    - /api/auth/login → user-service (포트 8005)
    - /api/friends → friend-service (포트 8003)
    - /api/messages → chat-service (포트 8002)

🛡️ 보안 기능:
    - JWT 토큰 검증 (로그인 확인)
    - Rate Limiting (요청 횟수 제한)
    - CORS 처리 (브라우저 보안)

💡 왜 Gateway가 필요한가요?
    1. 단일 진입점: 클라이언트는 하나의 주소만 알면 됨
    2. 보안 집중: 인증/보안을 한 곳에서 처리
    3. 라우팅: 요청을 올바른 서비스로 전달
    4. 로깅: 모든 요청을 한 곳에서 기록

🚀 실행 방법:
    uvicorn main:app --reload --port 8000
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.auth import AuthenticationMiddleware
from app.router import health_router, proxy_router
from app.utils import init_http_client, close_http_client, init_circuit_breaker


# =============================================================================
# 로깅 설정
# =============================================================================
# 로그는 프로그램이 무슨 일을 하는지 기록하는 일기장 같은 것입니다.
# 문제가 생겼을 때 로그를 보면 원인을 찾을 수 있습니다.
logging.basicConfig(
    level=logging.INFO,  # INFO 레벨 이상만 출력 (DEBUG < INFO < WARNING < ERROR)
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    # 출력 형식: "2024-01-15 10:30:45 - api-gateway - INFO - 메시지"
)
logger = logging.getLogger("api-gateway")


# =============================================================================
# 애플리케이션 생명주기 관리
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    📌 애플리케이션 생명주기 관리

    서버가 시작될 때와 종료될 때 실행되는 코드입니다.

    🟢 시작(Startup):
        - HTTP 클라이언트 초기화 (다른 서비스와 통신하기 위한 준비)

    🔴 종료(Shutdown):
        - HTTP 클라이언트 정리 (열어둔 연결 닫기)

    💡 왜 필요한가요?
        리소스를 제대로 정리하지 않으면 메모리 누수가 발생할 수 있습니다.
        마치 퇴근할 때 컴퓨터를 끄는 것처럼, 서버도 깔끔하게 정리해야 합니다.
    """
    # =========================================================================
    # 🟢 STARTUP - 서버 시작 시 실행
    # =========================================================================
    logger.info("🚀 API Gateway 시작 중...")

    # HTTP 클라이언트 초기화
    # - 다른 마이크로서비스(user-service 등)에 요청을 보내기 위한 클라이언트
    # - 매 요청마다 새로 만들지 않고 재사용하면 성능이 좋아집니다
    await init_http_client()
    logger.info("✅ HTTP 클라이언트 초기화 완료")

    # Circuit Breaker 초기화
    # - 서비스 장애 시 빠른 실패 (연쇄 장애 방지)
    # - 5번 실패 → OPEN, 60초 후 테스트
    init_circuit_breaker()
    logger.info("✅ Circuit Breaker 초기화 완료")

    # yield를 기준으로 위는 시작, 아래는 종료 시 실행됩니다
    yield

    # =========================================================================
    # 🔴 SHUTDOWN - 서버 종료 시 실행
    # =========================================================================
    logger.info("🛑 API Gateway 종료 중...")

    # HTTP 클라이언트 정리
    # - 열려있는 연결을 모두 닫습니다
    await close_http_client()
    logger.info("✅ HTTP 클라이언트 종료 완료")


# =============================================================================
# FastAPI 애플리케이션 인스턴스 생성
# =============================================================================
settings = get_settings()

app = FastAPI(
    title=settings.app_name,           # API 문서에 표시될 이름
    description="FastAPI-based API Gateway for BigTech Chat MSA",
    version="1.0.0",
    lifespan=lifespan,                 # 위에서 정의한 생명주기 관리자

    # API 문서 URL 설정
    # - /docs: Swagger UI (테스트하기 좋음)
    # - /redoc: ReDoc (읽기 좋음)
    # - 운영 환경에서는 보안을 위해 비활성화할 수 있습니다
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
)


# =============================================================================
# 미들웨어 등록
# =============================================================================
"""
📌 미들웨어란?
    요청과 응답 사이에서 실행되는 코드입니다.
    마치 공항의 보안 검색대처럼, 모든 요청이 여기를 통과합니다.

🔄 실행 순서 (양파처럼 겹겹이):
    요청 → [미들웨어1 → [미들웨어2 → [실제 처리] → 미들웨어2] → 미들웨어1] → 응답

    등록 순서가 중요합니다!
    - 마지막에 등록된 미들웨어가 가장 먼저 실행됩니다
    - 즉, 아래에서 위로 실행됩니다
"""

# -----------------------------------------------------------------------------
# CORS 미들웨어 (Cross-Origin Resource Sharing)
# -----------------------------------------------------------------------------
# 📌 CORS란?
#     브라우저 보안 정책입니다.
#     예: http://localhost:3000 (프론트엔드)에서
#         http://localhost:8000 (백엔드)로 요청하면
#     "다른 출처"이므로 브라우저가 기본적으로 차단합니다.
#
#     CORS 설정을 통해 "이 출처는 허용해도 돼"라고 알려줍니다.

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,      # 허용할 출처 목록 (예: ["http://localhost:3000"])
    allow_credentials=settings.cors_allow_credentials,  # 쿠키 전송 허용 여부
    allow_methods=settings.cors_allow_methods,          # 허용할 HTTP 메서드 (GET, POST 등)
    allow_headers=settings.cors_allow_headers,          # 허용할 헤더
)

# -----------------------------------------------------------------------------
# 인증 미들웨어 (JWT 검증) - Pure ASGI 구현
# -----------------------------------------------------------------------------
# 📌 Pure ASGI 방식으로 구현하여 request body 소비 버그 해결
#     - BaseHTTPMiddleware를 사용하지 않고 ASGI 인터페이스 직접 구현
#     - receive 함수를 가로채지 않아 body가 보존됨
#     - 헤더만 검사하고 body는 그대로 다음 앱에 전달
#
# 🔄 인증 흐름:
#     1. Authorization 헤더에서 Bearer 토큰 추출
#     2. JWT 토큰 검증 (서명, 만료시간)
#     3. 검증 성공 시 scope["state"]에 사용자 정보 저장
#     4. 프록시가 X-User-* 헤더로 백엔드 서비스에 전달
app.add_middleware(AuthenticationMiddleware)


# =============================================================================
# 라우터 등록
# =============================================================================
"""
📌 라우터란?
    URL 경로와 처리 함수를 연결하는 것입니다.

예시:
    - GET /health → health_router가 처리
    - GET /api/users → proxy_router가 user-service로 전달
"""

# 헬스 체크 라우터 (/health, /health/services)
app.include_router(health_router)

# 프록시 라우터 (/api/* → 백엔드 서비스로 전달)
app.include_router(proxy_router)


# =============================================================================
# 메인 실행 (개발 환경에서 직접 실행 시)
# =============================================================================
if __name__ == "__main__":
    import uvicorn

    # uvicorn: FastAPI를 실행하는 ASGI 서버
    # - host: 어떤 IP에서 접속을 받을지 (0.0.0.0 = 모든 IP)
    # - port: 포트 번호
    # - reload: 코드 변경 시 자동 재시작 (개발 환경에서만 사용)
    uvicorn.run(
        "main:app",          # main.py의 app 변수
        host=settings.host,  # 기본값: 0.0.0.0
        port=settings.port,  # 기본값: 8000
        reload=settings.debug,
        log_level="info"
    )
