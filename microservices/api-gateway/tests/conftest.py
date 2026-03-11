"""
API Gateway Test Configuration
"""

import pytest
import sys
from pathlib import Path

# api-gateway 디렉토리를 Python 경로에 추가
api_gateway_path = Path(__file__).parent.parent
sys.path.insert(0, str(api_gateway_path))


@pytest.fixture(scope="session")
def anyio_backend():
    """pytest-asyncio 백엔드 설정"""
    return "asyncio"
