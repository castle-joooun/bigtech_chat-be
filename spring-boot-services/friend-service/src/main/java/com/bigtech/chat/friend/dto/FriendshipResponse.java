package com.bigtech.chat.friend.dto;

import com.bigtech.chat.friend.entity.Friendship;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;

/**
 * 친구 관계 응답 DTO
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class FriendshipResponse {

    private Long id;
    private Long userId1;
    private Long userId2;
    private String status;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    public static FriendshipResponse from(Friendship friendship) {
        return FriendshipResponse.builder()
                .id(friendship.getId())
                .userId1(friendship.getUserId1())
                .userId2(friendship.getUserId2())
                .status(friendship.getStatus().name().toLowerCase())
                .createdAt(friendship.getCreatedAt())
                .updatedAt(friendship.getUpdatedAt())
                .build();
    }
}
