package com.bigtech.chat.user.dto;

import com.bigtech.chat.user.entity.User;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 사용자 프로필 응답 DTO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class UserProfileResponse {

    private Long id;
    private String username;
    private String displayName;
    private String statusMessage;
    private Boolean isOnline;
    private LocalDateTime lastSeenAt;

    public static UserProfileResponse from(User user) {
        return UserProfileResponse.builder()
                .id(user.getId())
                .username(user.getUsername())
                .displayName(user.getDisplayName())
                .statusMessage(user.getStatusMessage())
                .isOnline(user.getIsOnline())
                .lastSeenAt(user.getLastSeenAt())
                .build();
    }
}
