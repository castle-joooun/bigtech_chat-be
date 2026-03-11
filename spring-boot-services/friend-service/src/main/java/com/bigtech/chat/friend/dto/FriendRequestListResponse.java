package com.bigtech.chat.friend.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 친구 요청 목록 응답 DTO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class FriendRequestListResponse {

    private Long friendshipId;
    private Long userId;
    private String username;
    private String displayName;
    private String email;
    private String status;
    private LocalDateTime createdAt;
    private String requestType;  // "sent" or "received"
}
