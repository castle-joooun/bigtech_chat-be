import traceback
from typing import Callable, Union
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.exc import IntegrityError, OperationalError, DatabaseError
from pydantic import ValidationError as PydanticValidationError
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError, OperationFailure

from app.core.errors import (
    BaseCustomException,
    ValidationException,
    ValidationError,
    create_error_response,
    create_validation_error_response
)
from app.core.config import settings


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
                if "email" in error_detail.lower():
                    message = "Email already exists"
                elif "username" in error_detail.lower():
                    message = "Username already exists"
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
                    {"detail": error_detail}
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
                {"detail": error_detail if settings.debug else None}
            )

            # 로그 기록
            print(f"Database error: {type(e).__name__}: {str(e)}")

            return JSONResponse(
                status_code=error_response.status_code,
                content=error_response.model_dump()
            )

        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            # MongoDB 연결 에러
            error_response = create_error_response(
                "mongodb_connection_error",
                "MongoDB connection failed",
                status.HTTP_503_SERVICE_UNAVAILABLE,
                {"detail": str(e) if settings.debug else None}
            )

            # 로그 기록
            print(f"MongoDB connection error: {type(e).__name__}: {str(e)}")

            return JSONResponse(
                status_code=error_response.status_code,
                content=error_response.model_dump()
            )

        except OperationFailure as e:
            # MongoDB 작업 실패 (권한, 유효하지 않은 쿼리 등)
            error_response = create_error_response(
                "mongodb_operation_error",
                "MongoDB operation failed",
                status.HTTP_400_BAD_REQUEST,
                {"detail": str(e) if settings.debug else None}
            )

            # 로그 기록
            print(f"MongoDB operation error: {str(e)}")

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
                {"detail": str(e)}
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
                {"detail": str(e)}
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
                {"detail": str(e) if settings.debug else None}
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
                {"detail": str(e) if settings.debug else None}
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
            
            # 로그로 기록 (추후 로깅 시스템 구현 시 사용)
            print(f"Unhandled exception: {type(e).__name__}: {str(e)}")
            if settings.debug:
                print(traceback.format_exc())
            
            return JSONResponse(
                status_code=error_response.status_code,
                content=error_response.model_dump()
            )


def create_http_exception_handler():
    """FastAPI HTTPException 핸들러 생성"""
    async def http_exception_handler(request: Request, exc):
        """HTTPException을 표준 형식으로 변환"""
        
        # 우리의 커스텀 예외인 경우 그대로 반환
        if isinstance(exc, BaseCustomException):
            return JSONResponse(
                status_code=exc.status_code,
                content=exc.to_dict()
            )
        
        # 일반 HTTPException인 경우 표준 형식으로 변환
        error_response = create_error_response(
            "http_error",
            exc.detail if isinstance(exc.detail, str) else "HTTP error occurred",
            exc.status_code,
            {"detail": exc.detail} if not isinstance(exc.detail, str) else None
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response.model_dump()
        )
    
    return http_exception_handler