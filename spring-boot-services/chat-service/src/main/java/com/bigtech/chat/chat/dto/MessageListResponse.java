package com.bigtech.chat.chat.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 메시지 목록 응답 DTO
 *
 * FastAPI의 MessageListResponse와 동일한 구조.
 * 메시지 목록 + 페이지네이션 정보를 포함합니다.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MessageListResponse {

    private List<MessageResponse> messages;
    private int totalCount;
    private boolean hasMore;
}
