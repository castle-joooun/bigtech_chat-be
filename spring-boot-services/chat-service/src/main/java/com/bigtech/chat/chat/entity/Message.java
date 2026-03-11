package com.bigtech.chat.chat.entity;

import lombok.*;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.Id;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.mongodb.core.index.CompoundIndex;
import org.springframework.data.mongodb.core.index.CompoundIndexes;
import org.springframework.data.mongodb.core.index.Indexed;
import org.springframework.data.mongodb.core.index.TextIndexed;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.LocalDateTime;

/**
 * 메시지 엔티티 (MongoDB)
 *
 * 인덱스 전략 (FastAPI와 동일):
 * 1. room_created_idx: 채팅방별 메시지 최신순 조회
 * 2. user_room_idx: 사용자별 채팅방 메시지 조회
 * 3. room_deleted_created_idx: Soft Delete 필터링 + 시간순 정렬
 * 4. message_type_created_idx: 메시지 타입별 시간순 조회
 * 5. content (text index): 메시지 내용 텍스트 검색
 */
@Document(collection = "messages")
@CompoundIndexes({
        @CompoundIndex(name = "room_created_idx", def = "{'roomId': 1, 'createdAt': -1}"),
        @CompoundIndex(name = "user_room_idx", def = "{'userId': 1, 'roomId': 1}"),
        @CompoundIndex(name = "room_deleted_created_idx", def = "{'roomId': 1, 'isDeleted': 1, 'createdAt': -1}"),
        @CompoundIndex(name = "message_type_created_idx", def = "{'messageType': 1, 'createdAt': -1}")
})
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class Message {

    @Id
    private String id;

    @Indexed
    private Long userId;

    @Indexed
    private Long roomId;

    @Builder.Default
    private String roomType = "private";  // "private" or "group"

    @TextIndexed
    private String content;

    @Builder.Default
    private String messageType = "text";  // "text", "image", "file"

    // 파일/이미지 관련 필드
    private String fileUrl;
    private String fileName;
    private Integer fileSize;
    private String fileType;

    // 삭제 관련 필드 (Soft Delete)
    @Builder.Default
    private Boolean isDeleted = false;
    private LocalDateTime deletedAt;
    private Long deletedBy;

    // 수정 관련 필드
    @Builder.Default
    private Boolean isEdited = false;
    private LocalDateTime editedAt;
    private String originalContent;

    @CreatedDate
    private LocalDateTime createdAt;

    @LastModifiedDate
    private LocalDateTime updatedAt;

    /**
     * 메시지 삭제 (소프트 삭제)
     */
    public void delete(Long deletedByUserId) {
        this.isDeleted = true;
        this.deletedAt = LocalDateTime.now();
        this.deletedBy = deletedByUserId;
    }

    /**
     * 메시지 내용 수정
     */
    public void editContent(String newContent) {
        if (!this.isEdited) {
            this.originalContent = this.content;
        }
        this.content = newContent;
        this.isEdited = true;
        this.editedAt = LocalDateTime.now();
    }
}
