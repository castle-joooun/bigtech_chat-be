"""
shared_lib Test Configuration
"""

import pytest
import sys
from pathlib import Path

# shared_lib 디렉토리를 Python 경로에 추가
shared_lib_root = Path(__file__).parent.parent
sys.path.insert(0, str(shared_lib_root))


@pytest.fixture(scope="session")
def anyio_backend():
    """pytest-asyncio 백엔드 설정"""
    return "asyncio"
