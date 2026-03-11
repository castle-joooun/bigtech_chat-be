package com.bigtech.chat.common.kafka.events;

import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * 온라인 상태 변경 이벤트
 */
@Data
@EqualsAndHashCode(callSuper = true)
@NoArgsConstructor
public class UserOnlineStatusChangedEvent extends DomainEvent {

    private Long userId;
    private Boolean isOnline;

    public UserOnlineStatusChangedEvent(Long userId, Boolean isOnline) {
        super(LocalDateTime.now());
        this.userId = userId;
        this.isOnline = isOnline;
    }

    @Override
    public Map<String, Object> toMap() {
        Map<String, Object> map = super.toMap();
        map.put("user_id", userId);
        map.put("is_online", isOnline);
        return map;
    }
}
