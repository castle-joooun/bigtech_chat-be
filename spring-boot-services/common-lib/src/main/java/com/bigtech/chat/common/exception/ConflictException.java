package com.bigtech.chat.common.exception;

/**
 * 충돌 예외 (중복 리소스 등)
 */
public class ConflictException extends BaseException {

    public ConflictException(ErrorCode errorCode) {
        super(errorCode);
    }

    public ConflictException(ErrorCode errorCode, String message) {
        super(errorCode, message);
    }

    public ConflictException(String message) {
        super(ErrorCode.EMAIL_ALREADY_EXISTS, message);
    }
}
