package com.bigtech.chat.chat.service;

import com.bigtech.chat.chat.dto.ChatRoomResponse;
import com.bigtech.chat.chat.dto.MessageResponse;
import com.bigtech.chat.chat.entity.ChatRoom;
import com.bigtech.chat.chat.entity.Message;
import com.bigtech.chat.chat.entity.MessageReadStatus;
import com.bigtech.chat.chat.repository.ChatRoomRepository;
import com.bigtech.chat.chat.repository.MessageReadStatusRepository;
import com.bigtech.chat.chat.repository.MessageRepository;
import com.bigtech.chat.common.cache.CacheService;
import com.bigtech.chat.common.client.UserProfile;
import com.bigtech.chat.common.client.UserServiceClient;
import com.bigtech.chat.common.exception.BusinessLogicException;
import com.bigtech.chat.common.exception.ErrorCode;
import com.bigtech.chat.common.exception.ResourceNotFoundException;
import com.bigtech.chat.common.kafka.KafkaProducerService;
import com.bigtech.chat.common.kafka.events.ChatRoomCreatedEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.*;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * 채팅방 서비스
 *
 * MSA 원칙에 따라 User 정보는 user-service API를 통해 조회합니다.
 */
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
@Slf4j
public class ChatRoomService {

    private final ChatRoomRepository chatRoomRepository;
    private final MessageRepository messageRepository;
    private final MessageReadStatusRepository messageReadStatusRepository;
    private final CacheService cacheService;
    private final UserServiceClient userServiceClient;
    private final KafkaProducerService kafkaProducerService;

    @Value("${kafka.topics.message-events:message.events}")
    private String messageEventsTopic;

    private static final String CHAT_ROOMS_CACHE_PREFIX = "chat:rooms:user:";
    private static final int CHAT_ROOMS_CACHE_TTL = 60; // FastAPI와 동일: CacheTTL.MEDIUM = 60초

    /**
     * 채팅방 목록 조회 (Redis 캐시 적용)
     *
     * FastAPI와 동일한 Cache-Aside 패턴:
     * 1. Redis 캐시 조회 (TTL 60초)
     * 2. 캐시 MISS 시 DB + user-service 조회
     * 3. 결과 Redis에 저장
     *
     * user-service API를 통해 상대방 정보를 조회합니다.
     */
    @SuppressWarnings("unchecked")
    public List<ChatRoomResponse> getChatRooms(Long userId, int skip, int limit) {
        String cacheKey = CHAT_ROOMS_CACHE_PREFIX + userId;

        // 1. Redis 캐시 조회 (TTL 60초)
        Optional<List> cached = cacheService.get(cacheKey, List.class);
        if (cached.isPresent()) {
            log.debug("Chat rooms cache HIT: userId={}", userId);
            return cached.get();
        }

        // 2. 캐시 MISS: DB 조회
        log.debug("Chat rooms cache MISS: userId={}", userId);
        Pageable pageable = org.springframework.data.domain.PageRequest.of(skip / Math.max(limit, 1), Math.max(limit, 1));
        List<ChatRoom> rooms = chatRoomRepository.findByUserId(userId, pageable);

        if (rooms.isEmpty()) {
            return new ArrayList<>();
        }

        // 상대방 ID 목록 추출
        List<Long> otherUserIds = rooms.stream()
                .map(room -> room.getOtherUserId(userId))
                .collect(Collectors.toList());

        // user-service API로 사용자 정보 일괄 조회
        List<UserProfile> users = userServiceClient.getUsersByIds(otherUserIds);
        Map<Long, UserProfile> userMap = users.stream()
                .collect(Collectors.toMap(UserProfile::getId, Function.identity()));

        // 응답 생성
        List<ChatRoomResponse> responses = new ArrayList<>();
        for (ChatRoom room : rooms) {
            Long otherUserId = room.getOtherUserId(userId);
            UserProfile otherUser = userMap.get(otherUserId);

            ChatRoomResponse response = ChatRoomResponse.from(room, userId, otherUser);

            // 삭제되지 않은 마지막 메시지 조회
            Message lastMessage = messageRepository.findFirstActiveByRoomId(room.getId());
            if (lastMessage != null) {
                response.setLastMessage(MessageResponse.from(lastMessage, userId));
            }

            // 읽지 않은 메시지 수 계산
            response.setUnreadCount(calculateUnreadCount(room.getId(), userId));

            responses.add(response);
        }

        // 3. Redis 캐시 저장 (TTL 60초)
        if (!responses.isEmpty()) {
            cacheService.set(cacheKey, responses, CHAT_ROOMS_CACHE_TTL);
        }

        return responses;
    }

    /**
     * 채팅방 조회 또는 생성
     *
     * user-service API를 통해 대상 사용자 존재 여부를 확인합니다.
     */
    @Transactional
    public ChatRoomResponse getOrCreateChatRoom(Long currentUserId, Long targetUserId) {
        // 자기 자신과의 채팅방 불가
        if (currentUserId.equals(targetUserId)) {
            throw new BusinessLogicException(ErrorCode.CANNOT_CHAT_SELF);
        }

        // 대상 사용자 존재 확인 (user-service API 호출)
        Optional<UserProfile> targetUser = userServiceClient.getUserById(targetUserId);
        if (targetUser.isEmpty()) {
            throw new ResourceNotFoundException(ErrorCode.USER_NOT_FOUND);
        }

        // 기존 채팅방 확인
        Optional<ChatRoom> existing = chatRoomRepository.findByUsers(currentUserId, targetUserId);
        if (existing.isPresent()) {
            // 채팅방 타임스탬프 갱신 (FastAPI 동일: update_chat_room_timestamp)
            ChatRoom existingRoom = existing.get();
            existingRoom.touchUpdatedAt();
            chatRoomRepository.save(existingRoom);

            ChatRoomResponse response = ChatRoomResponse.from(existingRoom, currentUserId, targetUser.get());
            enrichChatRoomResponse(response, existingRoom.getId(), currentUserId);
            return response;
        }

        // 새 채팅방 생성 (user_id가 작은 쪽을 user1로 설정 - 중복 방지)
        Long user1 = Math.min(currentUserId, targetUserId);
        Long user2 = Math.max(currentUserId, targetUserId);
        ChatRoom chatRoom = ChatRoom.builder()
                .user1Id(user1)
                .user2Id(user2)
                .build();

        ChatRoom saved = chatRoomRepository.save(chatRoom);
        log.info("Chat room created: {} <-> {}, roomId={}", currentUserId, targetUserId, saved.getId());

        // 캐시 무효화
        invalidateCache(currentUserId);
        invalidateCache(targetUserId);

        // Kafka 이벤트 발행 (FastAPI와 동일)
        publishChatRoomCreatedEvent(saved, currentUserId);

        return ChatRoomResponse.from(saved, currentUserId, targetUser.get());
    }

    /**
     * 채팅방 조회
     */
    public ChatRoom getChatRoom(Long roomId) {
        return chatRoomRepository.findById(roomId)
                .orElseThrow(() -> new ResourceNotFoundException(ErrorCode.CHATROOM_NOT_FOUND));
    }

    /**
     * 채팅방 상세 조회 (상대방 정보 포함)
     */
    public ChatRoomResponse getChatRoomDetail(Long roomId, Long currentUserId) {
        ChatRoom room = getChatRoom(roomId);

        // 접근 권한 확인
        if (!room.hasUser(currentUserId)) {
            throw new BusinessLogicException(ErrorCode.CHATROOM_ACCESS_DENIED);
        }

        // 상대방 정보 조회
        Long otherUserId = room.getOtherUserId(currentUserId);
        Optional<UserProfile> otherUser = userServiceClient.getUserById(otherUserId);

        ChatRoomResponse response = ChatRoomResponse.from(room, currentUserId, otherUser.orElse(null));
        enrichChatRoomResponse(response, roomId, currentUserId);
        return response;
    }

    /**
     * 채팅방 접근 권한 확인
     */
    public void validateAccess(Long roomId, Long userId) {
        ChatRoom room = getChatRoom(roomId);
        if (!room.hasUser(userId)) {
            throw new BusinessLogicException(ErrorCode.CHATROOM_ACCESS_DENIED);
        }
    }

    /**
     * 채팅방 존재 확인
     */
    public boolean existsBetweenUsers(Long userId1, Long userId2) {
        return chatRoomRepository.existsByUsers(userId1, userId2);
    }

    /**
     * ChatRoomResponse에 last_message + unread_count 추가
     */
    private void enrichChatRoomResponse(ChatRoomResponse response, Long roomId, Long userId) {
        // 삭제되지 않은 마지막 메시지 조회
        Message lastMessage = messageRepository.findFirstActiveByRoomId(roomId);
        if (lastMessage != null) {
            response.setLastMessage(MessageResponse.from(lastMessage, userId));
        }

        // 읽지 않은 메시지 수 계산
        response.setUnreadCount(calculateUnreadCount(roomId, userId));
    }

    /**
     * 읽지 않은 메시지 수 계산
     *
     * FastAPI의 get_unread_count()와 동일한 로직:
     * 전체 메시지 - 읽은 메시지 - 내가 보낸 메시지 = 안 읽은 수
     */
    private int calculateUnreadCount(Long roomId, Long userId) {
        try {
            // 채팅방의 삭제되지 않은 모든 메시지 조회
            List<Message> allMessages = messageRepository.findActiveByRoomId(roomId, Pageable.unpaged());

            if (allMessages.isEmpty()) {
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

            return unreadCount;
        } catch (Exception e) {
            log.error("Failed to calculate unread count for room {}: {}", roomId, e.getMessage());
            return 0;
        }
    }

    private void invalidateCache(Long userId) {
        cacheService.delete(CHAT_ROOMS_CACHE_PREFIX + userId);
    }

    /**
     * 채팅방 생성 이벤트 발행 (FastAPI와 동일)
     */
    private void publishChatRoomCreatedEvent(ChatRoom chatRoom, Long creatorId) {
        try {
            ChatRoomCreatedEvent event = new ChatRoomCreatedEvent(
                    chatRoom.getId(),
                    "direct",
                    creatorId,
                    List.of(chatRoom.getUser1Id(), chatRoom.getUser2Id())
            );
            kafkaProducerService.publish(messageEventsTopic, event, String.valueOf(chatRoom.getId()));
        } catch (Exception e) {
            log.error("Failed to publish ChatRoomCreatedEvent: {}", e.getMessage());
        }
    }
}
