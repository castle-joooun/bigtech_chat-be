package com.bigtech.chat.common.exception;

import lombok.Getter;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;

/**
 * 에러 코드 정의
 */
@Getter
@RequiredArgsConstructor
public enum ErrorCode {

    // 400 Bad Request
    INVALID_INPUT(HttpStatus.BAD_REQUEST, "잘못된 입력입니다"),
    VALIDATION_FAILED(HttpStatus.BAD_REQUEST, "유효성 검증에 실패했습니다"),
    INVALID_PASSWORD_FORMAT(HttpStatus.BAD_REQUEST, "비밀번호는 8-16자, 영문+숫자+특수문자를 포함해야 합니다"),

    // 401 Unauthorized
    UNAUTHORIZED(HttpStatus.UNAUTHORIZED, "인증이 필요합니다"),
    INVALID_CREDENTIALS(HttpStatus.UNAUTHORIZED, "이메일 또는 비밀번호가 올바르지 않습니다"),
    INVALID_TOKEN(HttpStatus.UNAUTHORIZED, "유효하지 않은 토큰입니다"),
    EXPIRED_TOKEN(HttpStatus.UNAUTHORIZED, "만료된 토큰입니다"),

    // 403 Forbidden
    ACCESS_DENIED(HttpStatus.FORBIDDEN, "접근 권한이 없습니다"),

    // 404 Not Found
    USER_NOT_FOUND(HttpStatus.NOT_FOUND, "사용자를 찾을 수 없습니다"),
    CHATROOM_NOT_FOUND(HttpStatus.NOT_FOUND, "채팅방을 찾을 수 없습니다"),
    FRIENDSHIP_NOT_FOUND(HttpStatus.NOT_FOUND, "친구 관계를 찾을 수 없습니다"),
    MESSAGE_NOT_FOUND(HttpStatus.NOT_FOUND, "메시지를 찾을 수 없습니다"),
    RESOURCE_NOT_FOUND(HttpStatus.NOT_FOUND, "리소스를 찾을 수 없습니다"),

    // 409 Conflict
    EMAIL_ALREADY_EXISTS(HttpStatus.CONFLICT, "이미 사용 중인 이메일입니다"),
    USERNAME_ALREADY_EXISTS(HttpStatus.CONFLICT, "이미 사용 중인 사용자명입니다"),
    FRIENDSHIP_ALREADY_EXISTS(HttpStatus.CONFLICT, "이미 친구 관계가 존재합니다"),
    FRIEND_REQUEST_ALREADY_EXISTS(HttpStatus.CONFLICT, "이미 친구 요청이 존재합니다"),

    // 403 Forbidden (Chat specific)
    CHATROOM_ACCESS_DENIED(HttpStatus.FORBIDDEN, "채팅방 접근 권한이 없습니다"),
    MESSAGE_DELETE_FORBIDDEN(HttpStatus.FORBIDDEN, "메시지 삭제 권한이 없습니다"),
    MESSAGE_UPDATE_FORBIDDEN(HttpStatus.FORBIDDEN, "메시지 수정 권한이 없습니다"),

    // 422 Unprocessable Entity
    CANNOT_FRIEND_SELF(HttpStatus.UNPROCESSABLE_ENTITY, "자기 자신에게 친구 요청을 보낼 수 없습니다"),
    CANNOT_CHAT_SELF(HttpStatus.UNPROCESSABLE_ENTITY, "자기 자신과 채팅방을 만들 수 없습니다"),
    MESSAGE_CONTENT_EMPTY(HttpStatus.UNPROCESSABLE_ENTITY, "메시지 내용이 비어있습니다"),
    MESSAGE_CONTENT_TOO_LONG(HttpStatus.UNPROCESSABLE_ENTITY, "메시지는 300자를 초과할 수 없습니다"),
    MESSAGE_ALREADY_DELETED(HttpStatus.UNPROCESSABLE_ENTITY, "이미 삭제된 메시지입니다"),

    // 429 Too Many Requests
    RATE_LIMIT_EXCEEDED(HttpStatus.TOO_MANY_REQUESTS, "요청 횟수가 제한을 초과했습니다"),

    // 500 Internal Server Error
    INTERNAL_SERVER_ERROR(HttpStatus.INTERNAL_SERVER_ERROR, "서버 내부 오류가 발생했습니다"),
    KAFKA_PUBLISH_ERROR(HttpStatus.INTERNAL_SERVER_ERROR, "이벤트 발행에 실패했습니다"),
    CACHE_ERROR(HttpStatus.INTERNAL_SERVER_ERROR, "캐시 처리 중 오류가 발생했습니다"),

    // 502 Bad Gateway (MSA 서비스 간 통신 실패)
    EXTERNAL_SERVICE_ERROR(HttpStatus.BAD_GATEWAY, "외부 서비스 호출에 실패했습니다");

    private final HttpStatus httpStatus;
    private final String message;
}
