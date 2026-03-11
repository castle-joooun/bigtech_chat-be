package com.bigtech.chat.chat.service;

import com.bigtech.chat.chat.dto.MessageCreateRequest;
import com.bigtech.chat.chat.dto.MessageListResponse;
import com.bigtech.chat.chat.dto.MessageResponse;
import com.bigtech.chat.chat.entity.ChatRoom;
import com.bigtech.chat.chat.entity.Message;
import com.bigtech.chat.chat.repository.ChatRoomRepository;
import com.bigtech.chat.chat.repository.MessageRepository;
import com.bigtech.chat.common.cache.CacheService;
import com.bigtech.chat.common.exception.BusinessLogicException;
import com.bigtech.chat.common.exception.ErrorCode;
import com.bigtech.chat.common.exception.ResourceNotFoundException;
import com.bigtech.chat.common.kafka.KafkaProducerService;
import com.bigtech.chat.chat.entity.MessageReadStatus;
import com.bigtech.chat.chat.repository.MessageReadStatusRepository;
import com.bigtech.chat.common.kafka.events.MessageDeletedEvent;
import com.bigtech.chat.common.kafka.events.MessageSentEvent;
import com.bigtech.chat.common.kafka.events.MessagesReadEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import org.slf4j.MDC;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.Set;
import java.util.stream.Collectors;

/**
 * 메시지 서비스
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class MessageService {

    private final MessageRepository messageRepository;
    private final MessageReadStatusRepository messageReadStatusRepository;
    private final ChatRoomRepository chatRoomRepository;
    private final ChatRoomService chatRoomService;
    private final CacheService cacheService;
    private final KafkaProducerService kafkaProducerService;

    @Value("${kafka.topics.message-events:message.events}")
    private String messageEventsTopic;

    private static final String MESSAGE_CACHE_PREFIX = "chat:messages:";
    private static final int DEFAULT_PAGE_SIZE = 50;
    private static final int MAX_MESSAGE_LENGTH = 300;

    /**
     * 메시지 전송
     *
     * @param username JWT 토큰에서 추출한 사용자명 (user-service HTTP 호출 제거)
     */
    @Transactional
    public MessageResponse sendMessage(Long roomId, Long userId, String username, MessageCreateRequest request) {
        MDC.put("roomId", String.valueOf(roomId));
        MDC.put("userId", String.valueOf(userId));
        try {
            // 채팅방 접근 권한 확인
            chatRoomService.validateAccess(roomId, userId);

            // 메시지 길이 검증 (300자 제한)
            if (request.getContent() != null && request.getContent().length() > MAX_MESSAGE_LENGTH) {
                throw new BusinessLogicException(ErrorCode.MESSAGE_CONTENT_TOO_LONG);
            }

            // 메시지 생성
            Message message = Message.builder()
                    .userId(userId)
                    .roomId(roomId)
                    .roomType("private")
                    .content(request.getContent())
                    .messageType(request.getMessageType())
                    .build();

            Message saved = messageRepository.save(message);
            MDC.put("messageId", saved.getId());
            log.info("Message sent successfully");

            // 채팅방 updatedAt 갱신
            ChatRoom room = chatRoomService.getChatRoom(roomId);
            chatRoomRepository.save(room);

            // 캐시 무효화
            invalidateMessageCache(roomId);

            // 최근 메시지 LPUSH 캐시 (FastAPI와 동일)
            pushRecentMessage(roomId, saved, userId);

            // Kafka 이벤트 발행 (JWT username 사용 → user-service HTTP 호출 제거)
            publishMessageSentEvent(saved, room, username);

            return MessageResponse.from(saved, userId);
        } finally {
            MDC.clear();
        }
    }

    /**
     * 메시지 목록 조회
     *
     * FastAPI와 동일하게 MessageListResponse로 반환합니다.
     * 메시지 목록 + 전체 개수 + 더 로드 가능 여부를 포함합니다.
     */
    private static final String DEFAULT_ROOM_TYPE = "private";

    public MessageListResponse getMessages(Long roomId, Long userId, int skip, int limit) {
        // 채팅방 접근 권한 확인
        chatRoomService.validateAccess(roomId, userId);

        int actualLimit = limit > 0 ? limit : DEFAULT_PAGE_SIZE;
        int actualSkip = Math.max(skip, 0);
        // 페이지 번호 계산 (캐시 키용) - FastAPI와 동일: (skip // limit) + 1
        int pageNum = (actualLimit > 0) ? (actualSkip / actualLimit) + 1 : 1;
        String cacheKey = MESSAGE_CACHE_PREFIX + roomId + ":p" + pageNum;

        // 1. Redis 캐시 조회 (TTL 30초)
        Optional<MessageListResponse> cached = cacheService.get(cacheKey, MessageListResponse.class);
        if (cached.isPresent()) {
            return cached.get();
        }

        // 2. 캐시 MISS: MongoDB 조회 (FastAPI와 동일한 3중 필터: room_id + room_type + is_deleted)
        // skip/limit → page/size 변환 (Spring Data 내부용)
        int internalPage = (actualLimit > 0) ? actualSkip / actualLimit : 0;
        Pageable pageable = PageRequest.of(internalPage, actualLimit);

        // 삭제되지 않은 메시지만 조회 + room_type 필터 (Soft Delete 필터링)
        List<Message> messages = messageRepository.findActiveByRoomIdAndRoomTypeOrderByCreatedAtDesc(
                roomId, DEFAULT_ROOM_TYPE, pageable);

        // 삭제되지 않은 전체 메시지 수 조회 + room_type 필터
        long totalCount = messageRepository.countActiveByRoomIdAndRoomType(roomId, DEFAULT_ROOM_TYPE);

        // 메시지별 읽음 상태 일괄 조회 (N+1 → 1 batch query)
        List<String> messageIds = messages.stream()
                .map(Message::getId)
                .collect(Collectors.toList());
        List<MessageReadStatus> allReadStatuses = messageReadStatusRepository.findByMessageIdIn(messageIds);

        // messageId → readByUserIds 맵 생성
        Map<String, List<Long>> readStatusMap = allReadStatuses.stream()
                .collect(Collectors.groupingBy(
                        MessageReadStatus::getMessageId,
                        Collectors.mapping(MessageReadStatus::getUserId, Collectors.toList())
                ));

        List<MessageResponse> messageResponses = new java.util.ArrayList<>(messages.stream()
                .map(m -> {
                    List<Long> readByUserIds = readStatusMap.getOrDefault(m.getId(), List.of());
                    return MessageResponse.from(m, userId, readByUserIds);
                })
                .collect(Collectors.toList()));
        // DB에서 최신순(DESC)으로 조회 → 역순 변환(오래된순)으로 클라이언트 표시
        java.util.Collections.reverse(messageResponses);

        boolean hasMore = (actualSkip + messages.size()) < totalCount;

        MessageListResponse response = MessageListResponse.builder()
                .messages(messageResponses)
                .totalCount((int) totalCount)
                .hasMore(hasMore)
                .build();

        // 3. Redis 캐시 저장 (TTL 30초)
        cacheService.set(cacheKey, response, 30);

        return response;
    }

    /**
     * 메시지 읽음 처리
     *
     * FastAPI와 동일하게 MongoDB에 MessageReadStatus를 저장하고,
     * 실제 읽음 처리된 수를 반환합니다 (중복 방지).
     */
    @Transactional
    public int markAsRead(Long roomId, Long userId, List<String> messageIds) {
        MDC.put("roomId", String.valueOf(roomId));
        MDC.put("userId", String.valueOf(userId));
        try {
            // 채팅방 접근 권한 확인
            chatRoomService.validateAccess(roomId, userId);

            // 메시지가 해당 채팅방에 속하는지 검증 (FastAPI 동일: "All messages must be from the same room")
            for (String messageId : messageIds) {
                messageRepository.findById(messageId).ifPresent(message -> {
                    if (!message.getRoomId().equals(roomId)) {
                        throw new BusinessLogicException(ErrorCode.INVALID_INPUT);
                    }
                });
            }

            int readCount = 0;
            for (String messageId : messageIds) {
                // 중복 확인 (멱등성)
                boolean alreadyRead = messageReadStatusRepository
                        .findByMessageIdAndUserId(messageId, userId)
                        .isPresent();

                if (!alreadyRead) {
                    MessageReadStatus readStatus = MessageReadStatus.builder()
                            .messageId(messageId)
                            .userId(userId)
                            .roomId(roomId)
                            .readAt(LocalDateTime.now())
                            .build();
                    messageReadStatusRepository.save(readStatus);
                    readCount++;
                }
            }

            log.info("Messages marked as read: count={}, total={}", readCount, messageIds.size());

            // 읽음 처리 캐시 무효화
            invalidateUnreadCache(roomId, userId);

            // Kafka 이벤트 발행
            publishMessagesReadEvent(roomId, userId, messageIds);

            return readCount;
        } finally {
            MDC.clear();
        }
    }

    /**
     * 메시지 삭제
     */
    @Transactional
    public void deleteMessage(String messageId, Long userId) {
        MDC.put("messageId", messageId);
        MDC.put("userId", String.valueOf(userId));
        try {
            Message message = messageRepository.findById(messageId)
                    .orElseThrow(() -> new ResourceNotFoundException(ErrorCode.MESSAGE_NOT_FOUND));

            MDC.put("roomId", String.valueOf(message.getRoomId()));

            // 본인 메시지만 삭제 가능
            if (!message.getUserId().equals(userId)) {
                throw new BusinessLogicException(ErrorCode.MESSAGE_DELETE_FORBIDDEN);
            }

            message.delete(userId);
            messageRepository.save(message);
            log.info("Message deleted successfully");

            // 캐시 무효화
            invalidateMessageCache(message.getRoomId());

            // Kafka 이벤트 발행
            publishMessageDeletedEvent(message);
        } finally {
            MDC.clear();
        }
    }

    /**
     * 메시지 수정
     */
    @Transactional
    public MessageResponse updateMessage(String messageId, Long userId, String newContent) {
        MDC.put("messageId", messageId);
        MDC.put("userId", String.valueOf(userId));
        try {
            Message message = messageRepository.findById(messageId)
                    .orElseThrow(() -> new ResourceNotFoundException(ErrorCode.MESSAGE_NOT_FOUND));

            MDC.put("roomId", String.valueOf(message.getRoomId()));

            // 본인 메시지만 수정 가능
            if (!message.getUserId().equals(userId)) {
                throw new BusinessLogicException(ErrorCode.MESSAGE_UPDATE_FORBIDDEN);
            }

            // 삭제된 메시지는 수정 불가
            if (message.getIsDeleted()) {
                throw new BusinessLogicException(ErrorCode.MESSAGE_ALREADY_DELETED);
            }

            // 메시지 길이 검증 (300자 제한 - sendMessage와 동일)
            if (newContent != null && newContent.length() > MAX_MESSAGE_LENGTH) {
                throw new BusinessLogicException(ErrorCode.MESSAGE_CONTENT_TOO_LONG);
            }

            // 빈 메시지 검증
            if (newContent == null || newContent.isBlank()) {
                throw new BusinessLogicException(ErrorCode.INVALID_INPUT);
            }

            message.editContent(newContent);
            Message saved = messageRepository.save(message);
            log.info("Message updated successfully");

            // 캐시 무효화
            invalidateMessageCache(message.getRoomId());

            return MessageResponse.from(saved, userId);
        } finally {
            MDC.clear();
        }
    }

    private static final String RECENT_MESSAGES_PREFIX = "chat:recent:";
    private static final int RECENT_MESSAGES_MAX = 100;
    private static final int RECENT_MESSAGES_TTL = 60;

    private void invalidateMessageCache(Long roomId) {
        cacheService.deletePattern(MESSAGE_CACHE_PREFIX + roomId + ":*");
    }

    /**
     * 최근 메시지 LPUSH 캐시 (FastAPI와 동일 - 경량화)
     * 새 메시지를 리스트 앞에 추가하고 최대 100개 유지
     *
     * FastAPI 동일: id, user_id, content[:100], created_at만 저장
     * → Redis 메모리 절약 + 직렬화/역직렬화 성능 향상
     */
    private static final int PREVIEW_CONTENT_LENGTH = 100;

    private void pushRecentMessage(Long roomId, Message message, Long userId) {
        try {
            // 경량 데이터만 캐시 (FastAPI와 동일)
            Map<String, Object> lightweightData = Map.of(
                    "id", message.getId(),
                    "user_id", message.getUserId(),
                    "content", message.getContent() != null
                            ? message.getContent().substring(0, Math.min(message.getContent().length(), PREVIEW_CONTENT_LENGTH))
                            : "",
                    "created_at", message.getCreatedAt().toString()
            );
            cacheService.listPush(
                    RECENT_MESSAGES_PREFIX + roomId,
                    lightweightData,
                    RECENT_MESSAGES_MAX,
                    RECENT_MESSAGES_TTL
            );
        } catch (Exception e) {
            log.warn("Failed to push recent message cache: roomId={}, error={}", roomId, e.getMessage());
        }
    }

    private void invalidateUnreadCache(Long roomId, Long userId) {
        cacheService.delete("chat:unread:" + roomId + ":" + userId);
    }

    private void publishMessageSentEvent(Message message, ChatRoom room, String username) {
        try {
            // JWT 토큰에서 username 직접 사용 (user-service HTTP 호출 제거 → 레이턴시 개선)
            MessageSentEvent event = new MessageSentEvent(
                    message.getId(),
                    message.getRoomId(),
                    message.getUserId(),
                    username,
                    message.getContent(),
                    message.getMessageType()
            );
            // 파티션 키: room_id로 통일 → 같은 채팅방의 메시지 순서 보장
            kafkaProducerService.publish(messageEventsTopic, event, String.valueOf(message.getRoomId()));
        } catch (Exception e) {
            log.error("Failed to publish MessageSentEvent: {}", e.getMessage());
        }
    }

    private void publishMessagesReadEvent(Long roomId, Long userId, List<String> messageIds) {
        try {
            MessagesReadEvent event = new MessagesReadEvent(
                    roomId,
                    userId,
                    messageIds
            );
            kafkaProducerService.publish(messageEventsTopic, event, String.valueOf(roomId));
        } catch (Exception e) {
            log.error("Failed to publish MessagesReadEvent: {}", e.getMessage());
        }
    }

    private void publishMessageDeletedEvent(Message message) {
        try {
            MessageDeletedEvent event = new MessageDeletedEvent(
                    message.getId(),
                    message.getRoomId(),
                    message.getUserId()
            );
            // 파티션 키: room_id로 통일 → 같은 채팅방의 이벤트 순서 보장
            kafkaProducerService.publish(messageEventsTopic, event, String.valueOf(message.getRoomId()));
        } catch (Exception e) {
            log.error("Failed to publish MessageDeletedEvent: {}", e.getMessage());
        }
    }

    /**
     * 읽지 않은 메시지 수 조회 (Redis 캐시 적용)
     *
     * FastAPI와 동일한 로직:
     * 1. Redis 캐시 조회 (TTL 60초)
     * 2. 캐시 MISS 시 MongoDB에서 계산
     * 3. 전체 메시지 - 읽은 메시지 - 내가 보낸 메시지 = 안 읽은 수
     */
    public int getUnreadCount(Long roomId, Long userId) {
        // 채팅방 접근 권한 확인
        chatRoomService.validateAccess(roomId, userId);

        String cacheKey = "chat:unread:" + roomId + ":" + userId;

        // 1. Redis 캐시 조회
        Optional<Integer> cached = cacheService.get(cacheKey, Integer.class);
        if (cached.isPresent()) {
            return cached.get();
        }

        // 2. 캐시 MISS: MongoDB에서 계산
        // 채팅방의 삭제되지 않은 모든 메시지 조회
        List<Message> allMessages = messageRepository.findActiveByRoomId(
                roomId, Pageable.unpaged());

        if (allMessages.isEmpty()) {
            cacheService.set(cacheKey, 0, 60);
            return 0;
        }

        // 읽은 메시지 ID 조회
        List<MessageReadStatus> readStatuses = messageReadStatusRepository
                .findByRoomIdAndUserId(roomId, userId);
        Set<String> readMessageIds = readStatuses.stream()
                .map(MessageReadStatus::getMessageId)
                .collect(Collectors.toSet());

        // 읽지 않은 메시지 수 계산 (자신이 보낸 메시지 제외)
        int unreadCount = 0;
        for (Message message : allMessages) {
            if (!message.getUserId().equals(userId) && !readMessageIds.contains(message.getId())) {
                unreadCount++;
            }
        }

        // 3. Redis 캐시 저장 (TTL 60초) - Integer 타입으로 통일
        cacheService.set(cacheKey, unreadCount, 60);

        return unreadCount;
    }
}
