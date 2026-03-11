package com.bigtech.chat.chat.dto;

import com.bigtech.chat.chat.entity.ChatRoom;
import com.bigtech.chat.common.client.UserProfile;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 채팅방 응답 DTO
 *
 * FastAPI와 동일한 participants[] 배열 구조:
 * {
 *   "id": 123,
 *   "user1Id": 1,
 *   "user2Id": 2,
 *   "roomType": "direct",
 *   "participants": [
 *     {"id": 1, "username": "user1"},
 *     {"id": 2, "username": "user2"}
 *   ],
 *   "lastMessage": {...},
 *   "unreadCount": 3
 * }
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ChatRoomResponse {

    private Long id;
    private Long user1Id;
    private Long user2Id;
    private String roomType;
    private List<Map<String, Object>> participants;
    private MessageResponse lastMessage;
    private Integer unreadCount;
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    /**
     * ChatRoom 엔티티에서 DTO 생성 (기본값 사용)
     */
    public static ChatRoomResponse from(ChatRoom chatRoom, Long currentUserId) {
        Long otherId = chatRoom.getOtherUserId(currentUserId);
        return ChatRoomResponse.builder()
                .id(chatRoom.getId())
                .roomType("direct")
                .user1Id(chatRoom.getUser1Id())
                .user2Id(chatRoom.getUser2Id())
                .participants(List.of(
                        Map.of("id", currentUserId, "username", "Unknown"),
                        Map.of("id", otherId, "username", "Unknown")
                ))
                .unreadCount(0)
                .createdAt(chatRoom.getCreatedAt())
                .updatedAt(chatRoom.getUpdatedAt())
                .build();
    }

    /**
     * ChatRoom 엔티티와 UserProfile에서 DTO 생성
     *
     * FastAPI와 동일한 participants 구조:
     * [
     *   {"id": currentUserId, "username": currentUsername},
     *   {"id": otherUserId, "username": otherUsername}
     * ]
     */
    public static ChatRoomResponse from(ChatRoom chatRoom, Long currentUserId, UserProfile otherUser) {
        Long otherId = chatRoom.getOtherUserId(currentUserId);
        String otherUsername = (otherUser != null) ? otherUser.getUsername() : "Unknown";

        return ChatRoomResponse.builder()
                .id(chatRoom.getId())
                .roomType("direct")
                .user1Id(chatRoom.getUser1Id())
                .user2Id(chatRoom.getUser2Id())
                .participants(List.of(
                        Map.of("id", currentUserId, "username", "Unknown"),
                        Map.of("id", (Object) otherId, "username", otherUsername)
                ))
                .unreadCount(0)
                .createdAt(chatRoom.getCreatedAt())
                .updatedAt(chatRoom.getUpdatedAt())
                .build();
    }

    /**
     * ChatRoom 엔티티와 현재 사용자명 + 상대방 프로필에서 DTO 생성
     */
    public static ChatRoomResponse from(ChatRoom chatRoom, Long currentUserId, String currentUsername, UserProfile otherUser) {
        Long otherId = chatRoom.getOtherUserId(currentUserId);
        String otherUsername = (otherUser != null) ? otherUser.getUsername() : "Unknown";

        return ChatRoomResponse.builder()
                .id(chatRoom.getId())
                .roomType("direct")
                .user1Id(chatRoom.getUser1Id())
                .user2Id(chatRoom.getUser2Id())
                .participants(List.of(
                        Map.of("id", (Object) currentUserId, "username", currentUsername != null ? currentUsername : "Unknown"),
                        Map.of("id", (Object) otherId, "username", otherUsername)
                ))
                .unreadCount(0)
                .createdAt(chatRoom.getCreatedAt())
                .updatedAt(chatRoom.getUpdatedAt())
                .build();
    }
}
