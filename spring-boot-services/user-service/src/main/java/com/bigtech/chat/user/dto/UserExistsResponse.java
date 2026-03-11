package com.bigtech.chat.user.dto;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 사용자 존재 여부 응답 DTO
 *
 * 서비스 간 통신용 (friend-service, chat-service에서 사용)
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class UserExistsResponse {

    private Long userId;
    private Boolean exists;

    public static UserExistsResponse of(Long userId, boolean exists) {
        return new UserExistsResponse(userId, exists);
    }
}
