package com.bigtech.chat.chat.repository;

import com.bigtech.chat.chat.entity.ChatRoom;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import org.springframework.data.domain.Pageable;

import java.util.List;
import java.util.Optional;

/**
 * 채팅방 레포지토리 (MySQL)
 */
@Repository
public interface ChatRoomRepository extends JpaRepository<ChatRoom, Long> {

    /**
     * 두 사용자 간의 채팅방 조회 (양방향)
     */
    @Query("SELECT c FROM ChatRoom c WHERE " +
            "(c.user1Id = :userId1 AND c.user2Id = :userId2) OR " +
            "(c.user1Id = :userId2 AND c.user2Id = :userId1)")
    Optional<ChatRoom> findByUsers(
            @Param("userId1") Long userId1,
            @Param("userId2") Long userId2
    );

    /**
     * 사용자의 모든 채팅방 조회
     */
    @Query("SELECT c FROM ChatRoom c WHERE c.user1Id = :userId OR c.user2Id = :userId " +
            "ORDER BY c.updatedAt DESC")
    List<ChatRoom> findByUserId(@Param("userId") Long userId);

    /**
     * 사용자의 채팅방 조회 (페이지네이션)
     */
    @Query("SELECT c FROM ChatRoom c WHERE c.user1Id = :userId OR c.user2Id = :userId " +
            "ORDER BY c.updatedAt DESC")
    List<ChatRoom> findByUserId(@Param("userId") Long userId, Pageable pageable);

    /**
     * 채팅방 존재 여부 확인
     */
    @Query("SELECT CASE WHEN COUNT(c) > 0 THEN true ELSE false END FROM ChatRoom c WHERE " +
            "(c.user1Id = :userId1 AND c.user2Id = :userId2) OR " +
            "(c.user1Id = :userId2 AND c.user2Id = :userId1)")
    boolean existsByUsers(
            @Param("userId1") Long userId1,
            @Param("userId2") Long userId2
    );
}
