package com.bigtech.chat.common.exception;

/**
 * 리소스 미발견 예외
 */
public class ResourceNotFoundException extends BaseException {

    public ResourceNotFoundException(String resource) {
        super(ErrorCode.RESOURCE_NOT_FOUND, resource + "을(를) 찾을 수 없습니다");
    }

    public ResourceNotFoundException(String resource, Long id) {
        super(ErrorCode.RESOURCE_NOT_FOUND, resource + " (ID: " + id + ")을(를) 찾을 수 없습니다");
    }

    public ResourceNotFoundException(ErrorCode errorCode) {
        super(errorCode);
    }

    public ResourceNotFoundException(ErrorCode errorCode, String message) {
        super(errorCode, message);
    }
}
