package com.bigtech.chat.common.client;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * User Service에서 반환하는 사용자 프로필 DTO
 *
 * 서비스 간 통신용 - friend-service, chat-service에서 사용
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserProfile {

    private Long id;
    private String username;
    private String displayName;
    private String email;
    private String statusMessage;
    private Boolean isOnline;
    private LocalDateTime lastSeenAt;
}
