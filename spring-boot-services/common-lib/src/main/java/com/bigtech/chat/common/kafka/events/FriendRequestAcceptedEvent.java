package com.bigtech.chat.common.kafka.events;

import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * 친구 요청 수락 이벤트
 */
@Data
@EqualsAndHashCode(callSuper = true)
@NoArgsConstructor
public class FriendRequestAcceptedEvent extends DomainEvent {

    private Long friendshipId;
    private Long requesterId;
    private String requesterUsername;
    private Long addresseeId;
    private String addresseeUsername;

    public FriendRequestAcceptedEvent(Long friendshipId, Long requesterId, String requesterUsername,
                                       Long addresseeId, String addresseeUsername) {
        super(LocalDateTime.now());
        this.friendshipId = friendshipId;
        this.requesterId = requesterId;
        this.requesterUsername = requesterUsername;
        this.addresseeId = addresseeId;
        this.addresseeUsername = addresseeUsername;
    }

    @Override
    public Map<String, Object> toMap() {
        Map<String, Object> map = super.toMap();
        map.put("friendship_id", friendshipId);
        map.put("requester_id", requesterId);
        map.put("requester_username", requesterUsername);
        map.put("addressee_id", addresseeId);
        map.put("addressee_username", addresseeUsername);
        return map;
    }
}
