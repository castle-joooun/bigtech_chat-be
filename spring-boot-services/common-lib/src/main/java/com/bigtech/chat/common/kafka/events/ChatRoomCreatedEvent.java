package com.bigtech.chat.common.kafka.events;

import lombok.Data;
import lombok.EqualsAndHashCode;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 채팅방 생성 이벤트
 *
 * 새 채팅방이 생성될 때 Kafka로 발행되어
 * 참여자에게 알림을 전달합니다.
 */
@Data
@EqualsAndHashCode(callSuper = true)
@NoArgsConstructor
public class ChatRoomCreatedEvent extends DomainEvent {

    private Long roomId;
    private String roomType;
    private Long creatorId;
    private List<Long> participantIds;

    public ChatRoomCreatedEvent(Long roomId, String roomType, Long creatorId, List<Long> participantIds) {
        super(LocalDateTime.now());
        this.roomId = roomId;
        this.roomType = roomType;
        this.creatorId = creatorId;
        this.participantIds = participantIds;
    }

    @Override
    public Map<String, Object> toMap() {
        Map<String, Object> map = super.toMap();
        map.put("room_id", roomId);
        map.put("room_type", roomType);
        map.put("creator_id", creatorId);
        map.put("participant_ids", participantIds);
        return map;
    }
}
