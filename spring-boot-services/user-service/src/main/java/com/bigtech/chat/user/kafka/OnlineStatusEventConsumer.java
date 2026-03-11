package com.bigtech.chat.user.kafka;

import com.bigtech.chat.user.sse.OnlineStatusSseManager;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

import java.util.Map;

/**
 * 온라인 상태 이벤트 Kafka Consumer
 *
 * Kafka에서 온라인 상태 변경 이벤트를 수신하여 SSE로 클라이언트에 브로드캐스트합니다.
 *
 * 이벤트 플로우:
 * 1. 사용자 A가 로그인 (AuthService.login)
 * 2. AuthService가 Kafka에 UserOnlineStatusChangedEvent 발행
 * 3. 이 Consumer가 이벤트 수신
 * 4. OnlineStatusSseManager를 통해 A의 친구들에게 브로드캐스트
 * 5. 친구들의 클라이언트가 SSE로 A의 온라인 상태 변경 수신
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class OnlineStatusEventConsumer {

    private final OnlineStatusSseManager sseManager;

    /**
     * 온라인 상태 이벤트 처리
     */
    @KafkaListener(
            topics = "${kafka.topics.user-online-status:user.online_status}",
            groupId = "${spring.application.name}-online-status-broadcaster",
            containerFactory = "kafkaListenerContainerFactory"
    )
    public void handleOnlineStatusEvent(Map<String, Object> eventData) {
        try {
            String eventType = (String) eventData.get("__event_type__");

            // UserOnlineStatusChangedEvent 처리
            if ("UserOnlineStatusChangedEvent".equals(eventType) ||
                    eventData.containsKey("is_online")) {
                handleStatusChanged(eventData);
            } else {
                log.debug("Unknown online status event type: {}", eventType);
            }

        } catch (Exception e) {
            log.error("Failed to process online status event: {}", e.getMessage(), e);
        }
    }

    /**
     * 사용자 이벤트 처리 (회원가입 등)
     */
    @KafkaListener(
            topics = "${kafka.topics.user-events:user.events}",
            groupId = "${spring.application.name}-user-events",
            containerFactory = "kafkaListenerContainerFactory"
    )
    public void handleUserEvent(Map<String, Object> eventData) {
        try {
            String eventType = (String) eventData.get("__event_type__");

            switch (eventType != null ? eventType : "") {
                case "UserRegisteredEvent" -> handleUserRegistered(eventData);
                case "UserProfileUpdatedEvent" -> handleUserProfileUpdated(eventData);
                default -> log.debug("Unhandled user event type: {}", eventType);
            }

        } catch (Exception e) {
            log.error("Failed to process user event: {}", e.getMessage(), e);
        }
    }

    /**
     * 온라인 상태 변경 처리
     */
    private void handleStatusChanged(Map<String, Object> eventData) {
        Long userId = toLong(eventData.get("user_id"));
        Boolean isOnline = toBoolean(eventData.get("is_online"));

        if (userId == null || isOnline == null) {
            log.warn("OnlineStatusChangedEvent missing user_id or is_online");
            return;
        }

        // SSE로 친구들에게 브로드캐스트
        sseManager.broadcastStatusChange(userId, isOnline);

        log.info("Processed online status change: userId={}, isOnline={}", userId, isOnline);
    }

    /**
     * 회원가입 이벤트 처리
     */
    private void handleUserRegistered(Map<String, Object> eventData) {
        Long userId = toLong(eventData.get("user_id"));
        String username = (String) eventData.get("username");

        log.info("User registered event received: userId={}, username={}", userId, username);
        // 필요시 추가 처리 (예: 환영 알림 등)
    }

    /**
     * 프로필 업데이트 이벤트 처리
     */
    private void handleUserProfileUpdated(Map<String, Object> eventData) {
        Long userId = toLong(eventData.get("user_id"));
        log.debug("User profile updated: userId={}", userId);
        // 필요시 추가 처리
    }

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

    private Boolean toBoolean(Object value) {
        if (value == null) return null;
        if (value instanceof Boolean) return (Boolean) value;
        if (value instanceof String) return Boolean.parseBoolean((String) value);
        return null;
    }
}
