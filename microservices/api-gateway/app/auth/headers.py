"""
User Headers Constants

Gateway에서 백엔드 서비스로 전달하는 사용자 정보 헤더 상수
백엔드 서비스에서도 이 상수를 사용하여 일관성 유지
"""

# Gateway에서 전달하는 인증 관련 헤더
X_USER_ID = "X-User-ID"
X_USER_EMAIL = "X-User-Email"
X_USER_USERNAME = "X-User-Username"
X_USER_AUTHENTICATED = "X-User-Authenticated"

# 요청 추적 헤더
X_REQUEST_ID = "X-Request-ID"
X_FORWARDED_FOR = "X-Forwarded-For"
X_REAL_IP = "X-Real-IP"
