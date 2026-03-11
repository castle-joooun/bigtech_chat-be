"""
Friend Service Models
=====================

MSA 원칙에 따라 User 모델은 포함하지 않습니다.
User 데이터는 user-service API를 통해 조회합니다.
"""

from app.models.friendship import Friendship

__all__ = ["Friendship"]
