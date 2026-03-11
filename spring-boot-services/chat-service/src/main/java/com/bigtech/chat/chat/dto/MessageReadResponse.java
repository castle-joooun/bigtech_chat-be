package com.bigtech.chat.chat.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 메시지 읽음 처리 응답 DTO
 *
 * FastAPI의 MessageReadResponse와 동일한 구조.
 * 읽음 처리 결과를 반환합니다.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MessageReadResponse {

    private boolean success;
    private int readCount;
    private String message;
}
