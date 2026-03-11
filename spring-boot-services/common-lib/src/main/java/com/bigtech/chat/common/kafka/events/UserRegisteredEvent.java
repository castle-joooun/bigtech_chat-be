package com.bigtech.chat.common.kafka.events;

import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * 사용자 등록 이벤트
 */
@Data
@EqualsAndHashCode(callSuper = true)
@NoArgsConstructor
public class UserRegisteredEvent extends DomainEvent {

    private Long userId;
    private String email;
    private String username;
    private String displayName;

    public UserRegisteredEvent(Long userId, String email, String username, String displayName) {
        super(LocalDateTime.now());
        this.userId = userId;
        this.email = email;
        this.username = username;
        this.displayName = displayName;
    }

    @Override
    public Map<String, Object> toMap() {
        Map<String, Object> map = super.toMap();
        map.put("user_id", userId);
        map.put("email", email);
        map.put("username", username);
        map.put("display_name", displayName);
        return map;
    }
}
