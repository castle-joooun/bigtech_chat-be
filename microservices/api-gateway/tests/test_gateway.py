"""
API Gateway Tests
"""
import pytest
from fastapi.testclient import TestClient


class TestHealthEndpoints:
    """헬스 체크 엔드포인트 테스트"""

    def test_health_check(self, client: TestClient):
        """Gateway 헬스 체크"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "api-gateway"

    def test_request_id_header(self, client: TestClient):
        """X-Request-ID 헤더 확인"""
        response = client.get("/health")
        assert "X-Request-ID" in response.headers

    def test_security_headers(self, client: TestClient):
        """보안 헤더 확인"""
        response = client.get("/health")
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"


class TestXSSProtection:
    """XSS 방어 테스트"""

    def test_block_script_tag(self, client: TestClient):
        """<script> 태그 차단"""
        response = client.get("/api/users/search", params={"query": "<script>alert(1)</script>"})
        assert response.status_code == 400

    def test_block_javascript_protocol(self, client: TestClient):
        """javascript: 프로토콜 차단"""
        response = client.get("/api/users/search", params={"query": "javascript:alert(1)"})
        assert response.status_code == 400

    def test_block_event_handler(self, client: TestClient):
        """이벤트 핸들러 차단"""
        response = client.get("/api/users/search", params={"query": "test onerror=alert(1)"})
        assert response.status_code == 400


class TestSQLInjectionProtection:
    """SQL Injection 방어 테스트"""

    def test_block_union_select(self, client: TestClient):
        """UNION SELECT 차단"""
        response = client.get("/api/users/search", params={"query": "' UNION SELECT * FROM users--"})
        assert response.status_code == 400

    def test_block_sql_comment(self, client: TestClient):
        """SQL 주석 차단"""
        response = client.get("/api/users/search", params={"query": "test; DROP TABLE users--"})
        assert response.status_code == 400

    def test_block_or_injection(self, client: TestClient):
        """OR 1=1 차단"""
        response = client.get("/api/users/search", params={"query": "' OR '1'='1"})
        assert response.status_code == 400


class TestProxyRouting:
    """프록시 라우팅 테스트"""

    def test_unknown_route_returns_404(self, client: TestClient):
        """알 수 없는 경로는 404 반환"""
        response = client.get("/api/unknown/path")
        assert response.status_code == 404


@pytest.fixture
def client():
    """테스트 클라이언트"""
    # Import here to avoid circular imports during testing
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from main import app
    from app.utils.http_client import init_http_client, close_http_client
    import asyncio

    # Initialize HTTP client for testing
    loop = asyncio.new_event_loop()
    loop.run_until_complete(init_http_client())

    with TestClient(app) as test_client:
        yield test_client

    # Cleanup
    loop.run_until_complete(close_http_client())
    loop.close()
