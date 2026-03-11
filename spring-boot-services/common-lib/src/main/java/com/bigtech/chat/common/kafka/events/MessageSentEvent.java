package com.bigtech.chat.common.kafka.events;

import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * 메시지 전송 이벤트
 */
@Data
@EqualsAndHashCode(callSuper = true)
@NoArgsConstructor
public class MessageSentEvent extends DomainEvent {

    private String messageId;
    private Long roomId;
    private Long userId;
    private String username;
    private String content;
    private String messageType;

    public MessageSentEvent(String messageId, Long roomId, Long userId, String username,
                            String content, String messageType) {
        super(LocalDateTime.now());
        this.messageId = messageId;
        this.roomId = roomId;
        this.userId = userId;
        this.username = username;
        this.content = content;
        this.messageType = messageType;
    }

    @Override
    public Map<String, Object> toMap() {
        Map<String, Object> map = super.toMap();
        map.put("message_id", messageId);
        map.put("room_id", roomId);
        map.put("user_id", userId);
        map.put("username", username);
        map.put("content", content);
        map.put("message_type", messageType);
        return map;
    }
}
