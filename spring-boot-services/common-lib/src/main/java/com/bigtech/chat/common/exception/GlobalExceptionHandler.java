package com.bigtech.chat.common.exception;

import com.bigtech.chat.common.dto.ErrorResponse;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.FieldError;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.stream.Collectors;

/**
 * 전역 예외 처리
 */
@RestControllerAdvice
@Slf4j
public class GlobalExceptionHandler {

    /**
     * BaseException 처리
     */
    @ExceptionHandler(BaseException.class)
    public ResponseEntity<ErrorResponse> handleBaseException(BaseException e) {
        log.error("BaseException: {} - {}", e.getErrorCode(), e.getMessage());

        ErrorResponse response = ErrorResponse.builder()
                .error(e.getErrorCode().name())
                .message(e.getMessage())
                .build();

        return ResponseEntity
                .status(e.getErrorCode().getHttpStatus())
                .body(response);
    }

    /**
     * Validation 예외 처리
     */
    @ExceptionHandler(MethodArgumentNotValidException.class)
    public ResponseEntity<ErrorResponse> handleValidationException(MethodArgumentNotValidException e) {
        String message = e.getBindingResult().getFieldErrors().stream()
                .map(this::formatFieldError)
                .collect(Collectors.joining(", "));

        log.warn("Validation failed: {}", message);

        ErrorResponse response = ErrorResponse.builder()
                .error(ErrorCode.VALIDATION_FAILED.name())
                .message(message)
                .build();

        return ResponseEntity
                .status(HttpStatus.BAD_REQUEST)
                .body(response);
    }

    /**
     * 외부 서비스 호출 실패 처리 (502 Bad Gateway)
     *
     * MSA 환경에서 user-service, friend-service 등 외부 서비스 호출 실패 시
     * FastAPI의 ExternalServiceException과 동일한 502 응답을 반환합니다.
     */
    @ExceptionHandler(ExternalServiceException.class)
    public ResponseEntity<ErrorResponse> handleExternalServiceException(ExternalServiceException e) {
        log.error("External service error: {} - {}", e.getErrorCode(), e.getMessage(), e);

        ErrorResponse response = ErrorResponse.builder()
                .error(e.getErrorCode().name())
                .message(e.getMessage())
                .build();

        return ResponseEntity
                .status(HttpStatus.BAD_GATEWAY)
                .body(response);
    }

    /**
     * 일반 예외 처리
     */
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ErrorResponse> handleException(Exception e) {
        log.error("Unexpected error: ", e);

        ErrorResponse response = ErrorResponse.builder()
                .error(ErrorCode.INTERNAL_SERVER_ERROR.name())
                .message("서버 오류가 발생했습니다")
                .build();

        return ResponseEntity
                .status(HttpStatus.INTERNAL_SERVER_ERROR)
                .body(response);
    }

    private String formatFieldError(FieldError error) {
        return error.getField() + ": " + error.getDefaultMessage();
    }
}
