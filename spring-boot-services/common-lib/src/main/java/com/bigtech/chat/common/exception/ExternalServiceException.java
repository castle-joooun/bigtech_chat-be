package com.bigtech.chat.common.exception;

/**
 * 외부 서비스 호출 실패 예외 (502 Bad Gateway)
 *
 * MSA 환경에서 서비스 간 통신 실패 시 사용합니다.
 * FastAPI의 ExternalServiceException과 동일한 역할을 합니다.
 *
 * 사용 예:
 * - user-service API 호출 실패
 * - friend-service API 호출 실패
 * - 외부 서비스 타임아웃
 */
public class ExternalServiceException extends BaseException {

    public ExternalServiceException(ErrorCode errorCode) {
        super(errorCode);
    }

    public ExternalServiceException(ErrorCode errorCode, String message) {
        super(errorCode, message);
    }

    public ExternalServiceException(ErrorCode errorCode, String message, Throwable cause) {
        super(errorCode, message, cause);
    }

    public ExternalServiceException(String serviceName) {
        super(ErrorCode.EXTERNAL_SERVICE_ERROR, serviceName + " 서비스 호출에 실패했습니다");
    }

    public ExternalServiceException(String serviceName, Throwable cause) {
        super(ErrorCode.EXTERNAL_SERVICE_ERROR, serviceName + " 서비스 호출에 실패했습니다", cause);
    }
}
