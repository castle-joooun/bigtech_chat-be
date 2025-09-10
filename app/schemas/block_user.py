from datetime import datetime
from typing import Optional, List, TYPE_CHECKING
from pydantic import BaseModel, Field, ConfigDict

if TYPE_CHECKING:
    from .user import UserProfile


class BlockUserBase(BaseModel):
    """사용자 차단 기본 스키마"""
    blocked_user_id: int = Field(..., description="차단할 사용자 ID")


class BlockUserCreate(BlockUserBase):
    """사용자 차단 생성 스키마"""
    reason: Optional[str] = Field(None, max_length=500, description="차단 이유")


class BlockUserResponse(BaseModel):
    """사용자 차단 응답 스키마"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="차단 관계 ID")
    user_id: int = Field(..., description="차단한 사용자 ID")
    blocked_user_id: int = Field(..., description="차단된 사용자 ID")
    created_at: datetime = Field(..., description="차단일시")


class BlockUserWithDetails(BlockUserResponse):
    """상세 정보가 포함된 사용자 차단 스키마"""
    blocker: Optional["UserProfile"] = Field(None, description="차단한 사용자 정보")
    blocked: Optional["UserProfile"] = Field(None, description="차단된 사용자 정보")
    reason: Optional[str] = Field(None, description="차단 이유")


class BlockUserList(BaseModel):
    """차단된 사용자 목록 스키마"""
    blocked_users: List[BlockUserWithDetails] = Field(..., description="차단된 사용자 목록")
    total: int = Field(..., description="차단된 사용자 총 수")
    page: int = Field(..., description="현재 페이지")
    limit: int = Field(..., description="페이지당 항목 수")


class UnblockUser(BaseModel):
    """사용자 차단 해제 스키마"""
    blocked_user_id: int = Field(..., description="차단 해제할 사용자 ID")


class BlockStatus(BaseModel):
    """차단 상태 확인 스키마"""
    user_id: int = Field(..., description="확인할 사용자 ID")
    is_blocked: bool = Field(..., description="차단 여부")
    is_blocking: bool = Field(..., description="내가 차단했는지 여부")
    blocked_at: Optional[datetime] = Field(None, description="차단일시")


class BulkBlockUsers(BaseModel):
    """다중 사용자 차단 스키마"""
    user_ids: List[int] = Field(..., min_length=1, max_length=50, description="차단할 사용자 ID 목록")
    reason: Optional[str] = Field(None, max_length=500, description="차단 이유")


class BlockReport(BaseModel):
    """사용자 신고 및 차단 스키마"""
    user_id: int = Field(..., description="신고할 사용자 ID")
    report_type: str = Field(..., description="신고 유형: spam, harassment, inappropriate, etc")
    description: str = Field(..., min_length=10, max_length=1000, description="신고 내용")
    evidence: Optional[List[str]] = Field(None, description="증거 자료 URL 목록")
    block_user: bool = Field(default=True, description="신고와 동시에 차단 여부")
