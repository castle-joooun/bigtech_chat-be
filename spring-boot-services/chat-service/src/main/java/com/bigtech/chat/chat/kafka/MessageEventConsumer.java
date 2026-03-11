package com.bigtech.chat.chat.kafka;

import com.bigtech.chat.chat.sse.SseEmitterManager;
import com.bigtech.chat.common.cache.CacheService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

import java.util.List;
import java.util.Map;

/**
 * 메시지 이벤트 Kafka Consumer
 *
 * Kafka에서 메시지 이벤트를 수신하여 SSE로 클라이언트에 브로드캐스트합니다.
 *
 * <h2>이벤트 플로우</h2>
 * <pre>
 * 1. 클라이언트 A → POST /api/messages/{roomId} → MessageService
 * 2. MessageService → Kafka (message.events 토픽) → MessageSentEvent 발행
 * 3. 이 Consumer가 이벤트 수신 (@KafkaListener)
 * 4. SseEmitterManager를 통해 해당 방의 모든 클라이언트에 브로드캐스트
 * 5. 클라이언트 B가 SSE 스트림으로 실시간 메시지 수신
 * </pre>
 *
 * <h2>아키텍처 차이 (Spring Boot vs FastAPI)</h2>
 * <pre>
 * [Spring Boot] 중앙집중형 Consumer
 * - 단일 @KafkaListener가 message.events 토픽의 모든 이벤트를 수신
 * - __event_type__ 필드로 이벤트 타입 라우팅 (switch문)
 * - SseEmitterManager가 SSE 연결을 중앙 관리 (ConcurrentHashMap)
 * - Consumer Group ID: {app-name}-sse-broadcaster
 * - 장점: 리소스 효율적, 커넥션 관리 용이, 수평 확장 시 파티션 자동 리밸런싱
 *
 * [FastAPI] 요청별 Consumer
 * - 각 SSE 연결마다 독립적인 AIOKafkaConsumer 인스턴스 생성
 * - Consumer Group에 고유 ID (f"sse-user-{user_id}-{uuid}")
 * - 연결 종료 시 Consumer도 함께 종료 (라이프사이클 결합)
 * - 장점: 구현 단순, 독립적 라이프사이클
 * - 단점: Kafka 커넥션 수 증가, Consumer Group 관리 복잡
 * </pre>
 *
 * <h2>지원 이벤트 타입</h2>
 * <ul>
 *   <li>MessageSentEvent - 새 메시지 전송 → new_message SSE</li>
 *   <li>MessagesReadEvent - 메시지 읽음 처리 → messages_read SSE</li>
 *   <li>MessageDeletedEvent - 메시지 삭제 → message_deleted SSE</li>
 *   <li>ChatRoomCreatedEvent - 채팅방 생성 → chat_room_created SSE + 캐시 무효화</li>
 * </ul>
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class MessageEventConsumer {

    private final SseEmitterManager sseEmitterManager;
    private final CacheService cacheService;

    private static final String CHAT_ROOMS_CACHE_PREFIX = "chat:rooms:user:";

    /**
     * 채팅 이벤트 처리
     *
     * @KafkaListener가 message.events 토픽을 구독하여
     * 새 메시지가 발행될 때마다 이 메서드가 호출됩니다.
     */
    @KafkaListener(
            topics = "${kafka.topics.message-events:message.events}",
            groupId = "${spring.application.name}-sse-broadcaster",
            containerFactory = "kafkaListenerContainerFactory"
    )
    public void handleChatEvent(Map<String, Object> eventData) {
        try {
            String eventType = (String) eventData.get("__event_type__");

            if (eventType == null) {
                // __event_type__이 없으면 message_id로 MessageSent 추정
                if (eventData.containsKey("message_id")) {
                    eventType = "MessageSent";
                } else if (eventData.containsKey("message_ids")) {
                    eventType = "MessagesRead";
                }
            }

            log.debug("Received chat event: type={}", eventType);

            // FastAPI와 통일된 이벤트 타입 네이밍 (Event 접미사 없음)
            switch (eventType) {
                case "MessageSent", "MessageSentEvent" -> handleMessageSent(eventData);
                case "MessagesRead", "MessagesReadEvent" -> handleMessagesRead(eventData);
                case "MessageDeleted", "MessageDeletedEvent" -> handleMessageDeleted(eventData);
                case "ChatRoomCreated", "ChatRoomCreatedEvent" -> handleChatRoomCreated(eventData);
                default -> log.debug("Unknown event type: {}", eventType);
            }

        } catch (Exception e) {
            log.error("Failed to process chat event: {}", e.getMessage(), e);
        }
    }

    /**
     * 메시지 전송 이벤트 처리
     *
     * 새 메시지가 발행되면 해당 채팅방의 모든 연결된 클라이언트에게 브로드캐스트
     */
    private void handleMessageSent(Map<String, Object> eventData) {
        Long roomId = toLong(eventData.get("room_id"));
        Long userId = toLong(eventData.get("user_id"));
        String messageId = (String) eventData.get("message_id");

        if (roomId == null) {
            log.warn("MessageSentEvent missing room_id");
            return;
        }

        // SSE로 브로드캐스트할 데이터 구성
        Map<String, Object> messageData = Map.of(
                "id", messageId != null ? messageId : "",
                "user_id", userId != null ? userId : 0,
                "username", eventData.getOrDefault("username", "Unknown"),
                "room_id", roomId,
                "content", eventData.getOrDefault("content", ""),
                "message_type", eventData.getOrDefault("message_type", "text"),
                "created_at", eventData.getOrDefault("timestamp", ""),
                "is_deleted", false
        );

        // 해당 방의 모든 클라이언트에게 브로드캐스트 (발신자 포함)
        sseEmitterManager.broadcastToRoom(roomId, "new_message", messageData);

        log.info("Broadcasted new_message to room {}: messageId={}", roomId, messageId);
    }

    /**
     * 메시지 읽음 이벤트 처리
     *
     * 메시지가 읽음 처리되면 해당 채팅방의 다른 사용자에게 알림
     */
    private void handleMessagesRead(Map<String, Object> eventData) {
        Long roomId = toLong(eventData.get("room_id"));
        Long userId = toLong(eventData.get("user_id"));

        if (roomId == null || userId == null) {
            log.warn("MessagesReadEvent missing room_id or user_id");
            return;
        }

        @SuppressWarnings("unchecked")
        List<String> messageIds = (List<String>) eventData.get("message_ids");

        Map<String, Object> readData = Map.of(
                "room_id", roomId,
                "user_id", userId,
                "message_ids", messageIds != null ? messageIds : List.of(),
                "timestamp", eventData.getOrDefault("timestamp", "")
        );

        // 읽은 사람 제외하고 브로드캐스트 (상대방에게만)
        sseEmitterManager.broadcastToRoomExcludingUser(roomId, userId, "messages_read", readData);

        log.debug("Broadcasted messages_read to room {} (excluding user {})", roomId, userId);
    }

    /**
     * 메시지 삭제 이벤트 처리
     */
    private void handleMessageDeleted(Map<String, Object> eventData) {
        Long roomId = toLong(eventData.get("room_id"));
        String messageId = (String) eventData.get("message_id");

        if (roomId == null || messageId == null) {
            log.warn("MessageDeletedEvent missing room_id or message_id");
            return;
        }

        Map<String, Object> deleteData = Map.of(
                "room_id", roomId,
                "message_id", messageId,
                "timestamp", eventData.getOrDefault("timestamp", "")
        );

        sseEmitterManager.broadcastToRoom(roomId, "message_deleted", deleteData);

        log.debug("Broadcasted message_deleted to room {}: messageId={}", roomId, messageId);
    }

    /**
     * 채팅방 생성 이벤트 처리
     *
     * 새 채팅방이 생성되면:
     * 1. 참여자들의 채팅방 목록 캐시 무효화
     * 2. 참여자들에게 SSE로 알림 (채팅방 목록 갱신 트리거)
     */
    private void handleChatRoomCreated(Map<String, Object> eventData) {
        Long roomId = toLong(eventData.get("room_id"));
        Long creatorId = toLong(eventData.get("creator_id"));
        String roomType = (String) eventData.getOrDefault("room_type", "direct");

        if (roomId == null) {
            log.warn("ChatRoomCreatedEvent missing room_id");
            return;
        }

        @SuppressWarnings("unchecked")
        List<?> participantIds = (List<?>) eventData.get("participant_ids");

        // 참여자 캐시 무효화 & SSE 알림
        if (participantIds != null) {
            Map<String, Object> notifyData = Map.of(
                    "room_id", roomId,
                    "room_type", roomType,
                    "creator_id", creatorId != null ? creatorId : 0,
                    "timestamp", eventData.getOrDefault("timestamp", "")
            );

            for (Object participantId : participantIds) {
                Long userId = toLong(participantId);
                if (userId != null) {
                    // 채팅방 목록 캐시 무효화
                    cacheService.delete(CHAT_ROOMS_CACHE_PREFIX + userId);

                    // SSE로 채팅방 생성 알림 (참여자에게 목록 갱신 트리거)
                    sseEmitterManager.sendToUser(userId, "chat_room_created", notifyData);
                }
            }
        }

        log.info("Handled ChatRoomCreatedEvent: roomId={}, creatorId={}", roomId, creatorId);
    }

    /**
     * Object를 Long으로 변환 (Integer, Long 모두 처리)
     */
    private Long toLong(Object value) {
        if (value == null) return null;
        if (value instanceof Long) return (Long) value;
        if (value instanceof Integer) return ((Integer) value).longValue();
        if (value instanceof String) {
            try {
                return Long.parseLong((String) value);
            } catch (NumberFormatException e) {
                return null;
            }
        }
        return null;
    }
}
