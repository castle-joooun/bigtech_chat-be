package com.bigtech.chat.user.dto;

import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 프로필 수정 요청 DTO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ProfileUpdateRequest {

    @Size(max = 100, message = "표시 이름은 100자를 초과할 수 없습니다")
    private String displayName;

    @Size(max = 500, message = "상태 메시지는 500자를 초과할 수 없습니다")
    private String statusMessage;
}
