package com.bigtech.chat.chat.repository;

import com.bigtech.chat.chat.entity.MessageReadStatus;
import org.springframework.data.mongodb.repository.MongoRepository;
import org.springframework.stereotype.Repository;

import java.util.List;
import java.util.Optional;

/**
 * 메시지 읽음 상태 레포지토리 (MongoDB)
 *
 * FastAPI의 MessageReadStatus 조회 로직과 동일한 쿼리를 제공합니다.
 */
@Repository
public interface MessageReadStatusRepository extends MongoRepository<MessageReadStatus, String> {

    /**
     * 특정 메시지에 대한 사용자의 읽음 상태 조회 (중복 방지용)
     */
    Optional<MessageReadStatus> findByMessageIdAndUserId(String messageId, Long userId);

    /**
     * 특정 채팅방에서 사용자가 읽은 메시지 목록 조회
     */
    List<MessageReadStatus> findByRoomIdAndUserId(Long roomId, Long userId);

    /**
     * 특정 메시지를 읽은 사용자 목록 조회
     */
    List<MessageReadStatus> findByMessageId(String messageId);

    /**
     * 여러 메시지의 읽음 상태 일괄 조회 (N+1 문제 해결)
     * getMessages()에서 메시지별로 개별 조회하던 것을 한 번의 쿼리로 처리
     */
    List<MessageReadStatus> findByMessageIdIn(List<String> messageIds);
}
