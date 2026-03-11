package com.bigtech.chat.common.kafka.events;

import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 메시지 읽음 처리 이벤트
 */
@Data
@EqualsAndHashCode(callSuper = true)
@NoArgsConstructor
public class MessagesReadEvent extends DomainEvent {

    private Long roomId;
    private Long userId;
    private List<String> messageIds;

    public MessagesReadEvent(Long roomId, Long userId, List<String> messageIds) {
        super(LocalDateTime.now());
        this.roomId = roomId;
        this.userId = userId;
        this.messageIds = messageIds;
    }

    @Override
    public Map<String, Object> toMap() {
        Map<String, Object> map = super.toMap();
        map.put("room_id", roomId);
        map.put("user_id", userId);
        map.put("message_ids", messageIds);
        return map;
    }
}
