package com.bigtech.chat.chat.entity;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.UpdateTimestamp;

import java.time.LocalDateTime;

/**
 * 1:1 채팅방 엔티티 (MySQL)
 */
@Entity
@Table(name = "chat_rooms", indexes = {
        @Index(name = "idx_chat_room_user1", columnList = "user1Id"),
        @Index(name = "idx_chat_room_user2", columnList = "user2Id"),
        @Index(name = "idx_chat_room_users", columnList = "user1Id, user2Id", unique = true)
})
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ChatRoom {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private Long user1Id;

    @Column(nullable = false)
    private Long user2Id;

    @CreationTimestamp
    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @UpdateTimestamp
    @Column(nullable = false)
    private LocalDateTime updatedAt;

    /**
     * 채팅방 타임스탬프 갱신 (FastAPI 동일: update_chat_room_timestamp)
     * 기존 채팅방 접근 시 updated_at을 현재 시간으로 갱신합니다.
     */
    public void touchUpdatedAt() {
        this.updatedAt = LocalDateTime.now();
    }

    /**
     * 채팅방에 사용자가 참여하고 있는지 확인
     */
    public boolean hasUser(Long userId) {
        return user1Id.equals(userId) || user2Id.equals(userId);
    }

    /**
     * 상대방 사용자 ID 조회
     */
    public Long getOtherUserId(Long userId) {
        if (user1Id.equals(userId)) {
            return user2Id;
        }
        return user1Id;
    }
}
