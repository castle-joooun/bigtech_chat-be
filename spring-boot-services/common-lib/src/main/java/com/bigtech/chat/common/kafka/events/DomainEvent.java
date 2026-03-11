package com.bigtech.chat.common.kafka.events;

import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * 도메인 이벤트 기본 클래스
 *
 * 모든 도메인 이벤트의 부모 클래스
 */
@Data
@NoArgsConstructor
public abstract class DomainEvent {

    protected String eventId;
    protected String eventType;
    protected LocalDateTime timestamp;

    public DomainEvent(LocalDateTime timestamp) {
        this.eventId = UUID.randomUUID().toString();
        // FastAPI와 동일한 네이밍: "MessageSentEvent" → "MessageSent"
        String className = this.getClass().getSimpleName();
        this.eventType = className.endsWith("Event") ? className.substring(0, className.length() - 5) : className;
        this.timestamp = timestamp != null ? timestamp : LocalDateTime.now();
    }

    /**
     * Kafka 전송용 Map 변환
     */
    public Map<String, Object> toMap() {
        Map<String, Object> map = new HashMap<>();
        map.put("event_id", eventId);
        map.put("__event_type__", eventType);
        map.put("timestamp", timestamp.toString());
        return map;
    }
}
