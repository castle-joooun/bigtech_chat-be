package com.bigtech.chat.common.exception;

/**
 * 비즈니스 로직 예외
 */
public class BusinessLogicException extends BaseException {

    public BusinessLogicException(ErrorCode errorCode) {
        super(errorCode);
    }

    public BusinessLogicException(ErrorCode errorCode, String message) {
        super(errorCode, message);
    }

    public BusinessLogicException(String message) {
        super(ErrorCode.INVALID_INPUT, message);
    }
}
