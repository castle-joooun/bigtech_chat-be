package com.bigtech.chat.friend.entity;

import jakarta.persistence.*;
import lombok.*;
import org.hibernate.annotations.SQLDelete;
import org.hibernate.annotations.SQLRestriction;

import java.time.LocalDateTime;

/**
 * 친구 관계 엔티티
 *
 * 양방향 관계 설계:
 * - 저장: (user_id_1=A, user_id_2=B) 한 번만
 * - 조회: OR 조건으로 양방향 검색
 *
 * 상태 머신:
 * pending ──accept──▶ accepted
 *    │
 *    │ reject/cancel
 *    ▼
 * deleted (soft)
 */
@Entity
@Table(name = "friendships", indexes = {
        @Index(name = "idx_user_id_1", columnList = "user_id_1"),
        @Index(name = "idx_user_id_2", columnList = "user_id_2")
}, uniqueConstraints = {
        @UniqueConstraint(columnNames = {"user_id_1", "user_id_2"})
})
@SQLDelete(sql = "UPDATE friendships SET deleted_at = NOW() WHERE id = ?")
@SQLRestriction("deleted_at IS NULL")
@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Builder
public class Friendship {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "user_id_1", nullable = false)
    private Long userId1;  // 요청자

    @Column(name = "user_id_2", nullable = false)
    private Long userId2;  // 대상자

    @Enumerated(EnumType.STRING)
    @Column(nullable = false, length = 20)
    @Builder.Default
    private FriendshipStatus status = FriendshipStatus.PENDING;

    @Column(name = "created_at", nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at", nullable = false)
    private LocalDateTime updatedAt;

    @Column(name = "deleted_at")
    private LocalDateTime deletedAt;

    @PrePersist
    protected void onCreate() {
        createdAt = LocalDateTime.now();
        updatedAt = LocalDateTime.now();
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = LocalDateTime.now();
    }

    /**
     * 친구 요청 수락
     */
    public void accept() {
        this.status = FriendshipStatus.ACCEPTED;
    }

    /**
     * 사용자가 관계에 포함되어 있는지 확인
     */
    public boolean containsUser(Long userId) {
        return userId1.equals(userId) || userId2.equals(userId);
    }

    /**
     * 상대방 ID 조회
     */
    public Long getOtherUserId(Long currentUserId) {
        return userId1.equals(currentUserId) ? userId2 : userId1;
    }

    /**
     * 요청 대기 상태인지 확인
     */
    public boolean isPending() {
        return status == FriendshipStatus.PENDING;
    }

    /**
     * 수락된 상태인지 확인
     */
    public boolean isAccepted() {
        return status == FriendshipStatus.ACCEPTED;
    }
}
