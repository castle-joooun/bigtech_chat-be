"""
시간 관련 유틸리티 함수
"""
from datetime import datetime
from typing import Optional


def format_relative_time(dt: Optional[datetime]) -> str:
    """
    datetime을 상대적 시간 표기로 변환합니다.

    Args:
        dt: datetime 객체 (None인 경우 "알 수 없음" 반환)

    Returns:
        str: 상대적 시간 표기
            - 5분 이내: "방금전"
            - 5분~59분: "n분 전"
            - 1시간~23시간: "n시간 전"
            - 1일 이상: "n일 전"

    Examples:
        >>> format_relative_time(datetime.utcnow())
        "방금전"
        >>> format_relative_time(datetime.utcnow() - timedelta(minutes=30))
        "30분 전"
    """
    if dt is None:
        return "알 수 없음"

    # 현재 시간과의 차이 계산
    now = datetime.utcnow()
    diff = now - dt

    # 초 단위로 변환
    total_seconds = diff.total_seconds()

    # 음수인 경우 (미래 시간) - 방금전으로 표시
    if total_seconds < 0:
        return "방금전"

    # 5분 이내
    if total_seconds < 300:  # 5 * 60
        return "방금전"

    # 1시간 이내 (5분 ~ 59분)
    if total_seconds < 3600:  # 60 * 60
        minutes = int(total_seconds // 60)
        return f"{minutes}분 전"

    # 24시간 이내 (1시간 ~ 23시간)
    if total_seconds < 86400:  # 24 * 60 * 60
        hours = int(total_seconds // 3600)
        return f"{hours}시간 전"

    # 1일 이상
    days = int(total_seconds // 86400)
    return f"{days}일 전"
