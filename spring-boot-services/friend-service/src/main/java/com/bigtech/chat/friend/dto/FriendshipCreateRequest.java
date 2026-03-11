package com.bigtech.chat.friend.dto;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 친구 요청 생성 DTO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class FriendshipCreateRequest {

    @NotNull(message = "대상 사용자 ID는 필수입니다")
    private Long userId2;

    @Size(max = 500, message = "메시지는 500자를 초과할 수 없습니다")
    private String message;
}
