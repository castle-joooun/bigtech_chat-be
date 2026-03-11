"""
통합 에러 처리 미들웨어 (Friend Service)

모든 예외를 캐치하고 표준화된 에러 응답을 반환합니다.
Friend Service는 MySQL만 사용합니다.
"""

import traceback
import logging
from typing import Callable
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.exc import IntegrityError, OperationalError, DatabaseError
from pydantic import ValidationError as PydanticValidationError

from shared_lib.core import (
    BaseCustomException,
    ValidationException,
    ValidationError,
    create_error_response,
    create_validation_error_response
)
from app.core.config import settings


logger = logging.getLogger(__name__)


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    통합 에러 처리 미들웨어

    모든 예외를 캐치하고 표준화된 에러 응답을 반환합니다.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response

        except BaseCustomException as e:
            # 우리가 정의한 커스텀 예외들
            return JSONResponse(
                status_code=e.status_code,
                content=e.to_dict()
            )

        except PydanticValidationError as e:
            # Pydantic 검증 에러
            validation_errors = []

            for error in e.errors():
                field_name = ".".join(str(loc) for loc in error["loc"])
                validation_errors.append(
                    ValidationError(
                        field=field_name,
                        message=error["msg"],
                        value=error.get("input")
                    )
                )

            error_response = create_validation_error_response(
                "Request validation failed",
                validation_errors
            )

            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=error_response.model_dump()
            )

        except IntegrityError as e:
            # 데이터베이스 무결성 제약 조건 위반
            error_detail = str(e.orig) if hasattr(e, 'orig') else str(e)

            # MySQL 에러 코드별 처리
            if "Duplicate entry" in error_detail:
                if "friendship" in error_detail.lower():
                    message = "Friendship already exists"
                else:
                    message = "Duplicate entry detected"

                error_response = create_error_response(
                    "duplicate_entry",
                    message,
                    status.HTTP_409_CONFLICT,
                    {"constraint": "unique"}
                )
            else:
                error_response = create_error_response(
                    "database_constraint",
                    "Database constraint violation",
                    status.HTTP_400_BAD_REQUEST,
                    {"detail": error_detail} if settings.debug else None
                )

            return JSONResponse(
                status_code=error_response.status_code,
                content=error_response.model_dump()
            )

        except (OperationalError, DatabaseError) as e:
            # MySQL 데이터베이스 연결/작업 에러
            error_detail = str(e.orig) if hasattr(e, 'orig') else str(e)

            error_response = create_error_response(
                "database_error",
                "Database connection or operation failed",
                status.HTTP_503_SERVICE_UNAVAILABLE,
                {"detail": error_detail} if settings.debug else None
            )

            logger.error(f"Database error: {type(e).__name__}: {str(e)}")

            return JSONResponse(
                status_code=error_response.status_code,
                content=error_response.model_dump()
            )

        except ValueError as e:
            # 값 에러 (타입 변환 실패 등)
            error_response = create_error_response(
                "value_error",
                str(e),
                status.HTTP_400_BAD_REQUEST
            )

            return JSONResponse(
                status_code=error_response.status_code,
                content=error_response.model_dump()
            )

        except PermissionError as e:
            # 권한 에러
            error_response = create_error_response(
                "permission_error",
                "Permission denied",
                status.HTTP_403_FORBIDDEN,
                {"detail": str(e)} if settings.debug else None
            )

            return JSONResponse(
                status_code=error_response.status_code,
                content=error_response.model_dump()
            )

        except FileNotFoundError as e:
            # 파일을 찾을 수 없음
            error_response = create_error_response(
                "file_not_found",
                "Required file not found",
                status.HTTP_404_NOT_FOUND,
                {"detail": str(e)} if settings.debug else None
            )

            return JSONResponse(
                status_code=error_response.status_code,
                content=error_response.model_dump()
            )

        except ConnectionError as e:
            # 연결 에러 (데이터베이스, 외부 API 등)
            error_response = create_error_response(
                "connection_error",
                "Service temporarily unavailable",
                status.HTTP_503_SERVICE_UNAVAILABLE,
                {"detail": str(e)} if settings.debug else None
            )

            return JSONResponse(
                status_code=error_response.status_code,
                content=error_response.model_dump()
            )

        except TimeoutError as e:
            # 시간 초과 에러
            error_response = create_error_response(
                "timeout_error",
                "Request timeout",
                status.HTTP_408_REQUEST_TIMEOUT,
                {"detail": str(e)} if settings.debug else None
            )

            return JSONResponse(
                status_code=error_response.status_code,
                content=error_response.model_dump()
            )

        except Exception as e:
            # 예상하지 못한 모든 에러들
            error_detail = None
            if settings.debug:
                error_detail = {
                    "exception": str(e),
                    "type": type(e).__name__,
                    "traceback": traceback.format_exc()
                }

            error_response = create_error_response(
                "internal_server_error",
                "An unexpected error occurred",
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                error_detail
            )

            logger.error(f"Unhandled exception: {type(e).__name__}: {str(e)}")
            if settings.debug:
                logger.error(traceback.format_exc())

            return JSONResponse(
                status_code=error_response.status_code,
                content=error_response.model_dump()
            )
