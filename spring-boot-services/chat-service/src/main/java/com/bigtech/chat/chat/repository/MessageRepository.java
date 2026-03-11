package com.bigtech.chat.chat.repository;

import com.bigtech.chat.chat.entity.Message;
import org.springframework.data.domain.Pageable;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.data.mongodb.repository.Query;
import org.springframework.stereotype.Repository;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 메시지 레포지토리 (MongoDB)
 */
@Repository
public interface MessageRepository extends MongoRepository<Message, String> {

    /**
     * 채팅방의 메시지 목록 조회 (최신순)
     */
    List<Message> findByRoomIdOrderByCreatedAtDesc(Long roomId, Pageable pageable);

    /**
     * 채팅방의 메시지 목록 조회 (과거순)
     */
    List<Message> findByRoomIdOrderByCreatedAtAsc(Long roomId, Pageable pageable);

    /**
     * 특정 시간 이후의 메시지 조회
     */
    @Query("{'roomId': ?0, 'createdAt': {'$gt': ?1}}")
    List<Message> findByRoomIdAndCreatedAtAfter(Long roomId, LocalDateTime after);

    /**
     * 채팅방의 최신 메시지 1건 조회
     */
    Message findFirstByRoomIdOrderByCreatedAtDesc(Long roomId);

    /**
     * 채팅방의 메시지 개수 조회
     */
    long countByRoomId(Long roomId);

    /**
     * 사용자가 보낸 메시지 목록 조회
     */
    List<Message> findByUserId(Long userId, Pageable pageable);

    /**
     * 삭제되지 않은 메시지만 조회
     */
    @Query("{'roomId': ?0, 'isDeleted': false}")
    List<Message> findActiveByRoomId(Long roomId, Pageable pageable);

    /**
     * 삭제되지 않은 메시지 목록 조회 (최신순, 페이지네이션)
     */
    @Query(value = "{'roomId': ?0, 'isDeleted': false}", sort = "{'createdAt': -1}")
    List<Message> findActiveByRoomIdOrderByCreatedAtDesc(Long roomId, Pageable pageable);

    /**
     * 삭제되지 않은 메시지 목록 조회 + room_type 필터 (최신순, 페이지네이션)
     * FastAPI의 get_room_messages()와 동일한 3중 필터:
     * {room_id, room_type, is_deleted: false}
     */
    @Query(value = "{'roomId': ?0, 'roomType': ?1, 'isDeleted': false}", sort = "{'createdAt': -1}")
    List<Message> findActiveByRoomIdAndRoomTypeOrderByCreatedAtDesc(Long roomId, String roomType, Pageable pageable);

    /**
     * 삭제되지 않은 메시지 개수 조회
     */
    @Query(value = "{'roomId': ?0, 'isDeleted': false}", count = true)
    long countActiveByRoomId(Long roomId);

    /**
     * 삭제되지 않은 메시지 개수 조회 + room_type 필터
     * FastAPI의 get_room_messages_count()와 동일
     */
    @Query(value = "{'roomId': ?0, 'roomType': ?1, 'isDeleted': false}", count = true)
    long countActiveByRoomIdAndRoomType(Long roomId, String roomType);

    /**
     * 삭제되지 않은 최신 메시지 1건 조회
     */
    @Query(value = "{'roomId': ?0, 'isDeleted': false}", sort = "{'createdAt': -1}")
    Message findFirstActiveByRoomId(Long roomId);
}
