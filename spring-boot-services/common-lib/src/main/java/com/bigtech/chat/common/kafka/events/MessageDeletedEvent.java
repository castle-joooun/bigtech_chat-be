package com.bigtech.chat.common.kafka.events;

import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * 메시지 삭제 이벤트
 *
 * 메시지가 소프트 삭제될 때 Kafka로 발행되어
 * SSE를 통해 실시간으로 클라이언트에 전달됩니다.
 */
@Data
@EqualsAndHashCode(callSuper = true)
@NoArgsConstructor
public class MessageDeletedEvent extends DomainEvent {

    private String messageId;
    private Long roomId;
    private Long deletedBy;

    public MessageDeletedEvent(String messageId, Long roomId, Long deletedBy) {
        super(LocalDateTime.now());
        this.messageId = messageId;
        this.roomId = roomId;
        this.deletedBy = deletedBy;
    }

    @Override
    public Map<String, Object> toMap() {
        Map<String, Object> map = super.toMap();
        map.put("message_id", messageId);
        map.put("room_id", roomId);
        map.put("deleted_by", deletedBy);
        return map;
    }
}
