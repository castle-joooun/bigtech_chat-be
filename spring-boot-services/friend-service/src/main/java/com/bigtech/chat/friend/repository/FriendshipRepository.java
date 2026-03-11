package com.bigtech.chat.friend.repository;

import com.bigtech.chat.friend.entity.Friendship;
import com.bigtech.chat.friend.entity.FriendshipStatus;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * 친구 관계 레포지토리
 */
@Repository
public interface FriendshipRepository extends JpaRepository<Friendship, Long> {

    /**
     * 양방향 친구 관계 조회
     */
    @Query("SELECT f FROM Friendship f WHERE " +
            "(f.userId1 = :userId1 AND f.userId2 = :userId2) OR " +
            "(f.userId1 = :userId2 AND f.userId2 = :userId1)")
    Optional<Friendship> findByUserIds(
            @Param("userId1") Long userId1,
            @Param("userId2") Long userId2
    );

    /**
     * 친구 요청 조회 (요청자 → 대상자, 대기 상태)
     */
    @Query("SELECT f FROM Friendship f WHERE " +
            "f.userId1 = :requesterId AND f.userId2 = :addresseeId AND " +
            "f.status = :status")
    Optional<Friendship> findByRequesterAndAddresseeAndStatus(
            @Param("requesterId") Long requesterId,
            @Param("addresseeId") Long addresseeId,
            @Param("status") FriendshipStatus status
    );

    /**
     * 수락된 친구 목록 조회
     */
    @Query("SELECT f FROM Friendship f WHERE " +
            "(f.userId1 = :userId OR f.userId2 = :userId) AND " +
            "f.status = 'ACCEPTED'")
    List<Friendship> findAcceptedFriendships(@Param("userId") Long userId);

    /**
     * 받은 친구 요청 목록 (대기 상태)
     */
    @Query("SELECT f FROM Friendship f WHERE " +
            "f.userId2 = :userId AND f.status = 'PENDING'")
    List<Friendship> findReceivedRequests(@Param("userId") Long userId);

    /**
     * 보낸 친구 요청 목록 (대기 상태)
     */
    @Query("SELECT f FROM Friendship f WHERE " +
            "f.userId1 = :userId AND f.status = 'PENDING'")
    List<Friendship> findSentRequests(@Param("userId") Long userId);

    /**
     * 친구 여부 확인
     */
    @Query("SELECT CASE WHEN COUNT(f) > 0 THEN true ELSE false END FROM Friendship f WHERE " +
            "((f.userId1 = :userId1 AND f.userId2 = :userId2) OR " +
            "(f.userId1 = :userId2 AND f.userId2 = :userId1)) AND " +
            "f.status = 'ACCEPTED'")
    boolean areFriends(
            @Param("userId1") Long userId1,
            @Param("userId2") Long userId2
    );
}
