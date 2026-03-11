"""
Shared Schemas
==============

마이크로서비스 간 공유되는 Pydantic 스키마입니다.
"""

from .user import UserProfile, UserProfileMinimal

__all__ = ["UserProfile", "UserProfileMinimal"]
