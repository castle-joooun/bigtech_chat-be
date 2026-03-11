package com.bigtech.chat.chat.dto;

import jakarta.validation.constraints.NotNull;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * 메시지 읽음 처리 요청 DTO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MessagesReadRequest {

    @NotNull(message = "채팅방 ID는 필수입니다")
    private Long roomId;

    @NotNull(message = "메시지 ID 목록은 필수입니다")
    private List<String> messageIds;
}
