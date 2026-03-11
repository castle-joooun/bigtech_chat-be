package com.bigtech.chat.chat.entity;

import lombok.*;
import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.index.CompoundIndex;
import org.springframework.data.mongodb.core.index.CompoundIndexes;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;

/**
 * 메시지 읽음 상태 엔티티 (MongoDB)
 *
 * 사용자가 메시지를 읽은 시점을 기록합니다.
 * FastAPI의 MessageReadStatus (message_read_status 컬렉션)와 동일한 구조.
 */
@Document(collection = "message_read_status")
@CompoundIndexes({
        @CompoundIndex(name = "room_user_read_idx", def = "{'roomId': 1, 'userId': 1, 'readAt': -1}"),
        @CompoundIndex(name = "message_user_idx", def = "{'messageId': 1, 'userId': 1}", unique = true),
        @CompoundIndex(name = "user_read_idx", def = "{'userId': 1, 'readAt': -1}")
})
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MessageReadStatus {

    @Id
    private String id;

    private String messageId;
    private Long userId;
    private Long roomId;

    @Builder.Default
    private LocalDateTime readAt = LocalDateTime.now();
}
