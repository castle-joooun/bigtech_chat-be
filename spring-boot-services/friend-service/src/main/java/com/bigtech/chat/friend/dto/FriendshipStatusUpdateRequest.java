package com.bigtech.chat.friend.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 친구 요청 상태 업데이트 DTO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class FriendshipStatusUpdateRequest {

    @NotBlank(message = "액션은 필수입니다")
    @Pattern(regexp = "^(accept|reject)$", message = "액션은 accept 또는 reject만 허용됩니다")
    private String action;
}
