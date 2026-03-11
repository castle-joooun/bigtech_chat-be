package com.bigtech.chat.chat.dto;

import com.bigtech.chat.chat.entity.Message;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 메시지 응답 DTO
 *
 * FastAPI의 MessageResponse 스키마와 동일한 필드 구조.
 * 기본 필드 + 파일 관련 + 삭제 관련 + 수정 관련 + 시간 정보 + 읽음 상태
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MessageResponse {

    // 기본 필드
    private String id;
    private Long userId;
    private String username;
    private String displayName;
    private Long roomId;
    private String roomType;
    private String content;
    private String messageType;

    // 파일/이미지 관련 필드
    private String fileUrl;
    private String fileName;
    private Integer fileSize;
    private String fileType;

    // 삭제 관련 필드 (Soft Delete)
    private Boolean isDeleted;
    private LocalDateTime deletedAt;

    // 수정 관련 필드
    private Boolean isEdited;
    private LocalDateTime editedAt;

    // 동적 필드
    private Boolean isMine;

    // 읽음 상태 (FastAPI 동일 필드)
    private List<Long> readBy;
    private Boolean isRead;

    // 시간 정보
    private LocalDateTime createdAt;
    private LocalDateTime updatedAt;

    /**
     * 기본 변환 (읽음 상태 미포함)
     * 메시지 전송, lastMessage 조회 등에서 사용
     */
    public static MessageResponse from(Message message, Long currentUserId) {
        return MessageResponse.builder()
                .id(message.getId())
                .userId(message.getUserId())
                .username("user_" + message.getUserId())  // Placeholder
                .displayName("User " + message.getUserId())  // Placeholder
                .roomId(message.getRoomId())
                .roomType(message.getRoomType())
                .content(message.getContent())
                .messageType(message.getMessageType())
                // 파일 관련
                .fileUrl(message.getFileUrl())
                .fileName(message.getFileName())
                .fileSize(message.getFileSize())
                .fileType(message.getFileType())
                // 삭제 관련
                .isDeleted(message.getIsDeleted())
                .deletedAt(message.getDeletedAt())
                // 수정 관련
                .isEdited(message.getIsEdited())
                .editedAt(message.getEditedAt())
                // 동적 필드
                .isMine(message.getUserId().equals(currentUserId))
                // 시간 정보
                .createdAt(message.getCreatedAt())
                .updatedAt(message.getUpdatedAt())
                .build();
    }

    /**
     * 읽음 상태 포함 변환 (FastAPI 동일)
     * 메시지 목록 조회에서 사용 - readBy, isRead 필드 포함
     *
     * @param message 메시지 엔티티
     * @param currentUserId 현재 사용자 ID
     * @param readByUserIds 해당 메시지를 읽은 사용자 ID 목록
     */
    public static MessageResponse from(Message message, Long currentUserId, List<Long> readByUserIds) {
        MessageResponse response = from(message, currentUserId);
        response.setReadBy(readByUserIds);
        response.setIsRead(readByUserIds != null && readByUserIds.contains(currentUserId));
        return response;
    }
}
