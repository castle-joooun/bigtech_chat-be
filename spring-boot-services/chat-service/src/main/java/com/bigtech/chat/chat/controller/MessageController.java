package com.bigtech.chat.chat.controller;

import com.bigtech.chat.chat.dto.*;
import com.bigtech.chat.chat.service.MessageService;
import com.bigtech.chat.common.security.CurrentUser;
import com.bigtech.chat.common.security.JwtPayload;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

/**
 * 메시지 컨트롤러
 *
 * FastAPI의 message.py API 엔드포인트와 동일한 구조.
 *
 * | Method | Path                                  | 설명              |
 * |--------|---------------------------------------|-------------------|
 * | POST   | /api/messages/{roomId}                | 메시지 전송        |
 * | GET    | /api/messages/{roomId}                | 메시지 목록 조회    |
 * | POST   | /api/messages/read                    | 읽음 처리          |
 * | GET    | /api/messages/room/{roomId}/unread-count | 안읽은 수 조회  |
 * | DELETE | /api/messages/{messageId}             | 메시지 삭제        |
 * | PUT    | /api/messages/{messageId}             | 메시지 수정        |
 */
@RestController
@RequestMapping("/api/messages")
@RequiredArgsConstructor
@Tag(name = "Messages", description = "메시지 관리 API")
public class MessageController {

    private final MessageService messageService;

    @PostMapping("/{roomId}")
    @Operation(summary = "메시지 전송")
    public ResponseEntity<MessageResponse> sendMessage(
            @CurrentUser JwtPayload currentUser,
            @PathVariable Long roomId,
            @Valid @RequestBody MessageCreateRequest request) {
        MessageResponse message = messageService.sendMessage(
                roomId,
                currentUser.getUserId(),
                currentUser.getUsername(),
                request
        );
        return ResponseEntity.status(HttpStatus.CREATED).body(message);
    }

    @GetMapping("/{roomId}")
    @Operation(summary = "메시지 목록 조회")
    public ResponseEntity<MessageListResponse> getMessages(
            @CurrentUser JwtPayload currentUser,
            @PathVariable Long roomId,
            @RequestParam(defaultValue = "50") int limit,
            @RequestParam(defaultValue = "0") int skip) {
        MessageListResponse response = messageService.getMessages(
                roomId,
                currentUser.getUserId(),
                skip,
                limit
        );
        return ResponseEntity.ok(response);
    }

    @PostMapping("/read")
    @Operation(summary = "메시지 읽음 처리")
    public ResponseEntity<MessageReadResponse> markAsRead(
            @CurrentUser JwtPayload currentUser,
            @Valid @RequestBody MessagesReadRequest request) {
        int readCount = messageService.markAsRead(
                request.getRoomId(),
                currentUser.getUserId(),
                request.getMessageIds()
        );
        return ResponseEntity.ok(MessageReadResponse.builder()
                .success(true)
                .readCount(readCount)
                .message(readCount + " messages marked as read")
                .build());
    }

    @GetMapping("/room/{roomId}/unread-count")
    @Operation(summary = "읽지 않은 메시지 수 조회")
    public ResponseEntity<Map<String, Integer>> getUnreadCount(
            @CurrentUser JwtPayload currentUser,
            @PathVariable Long roomId) {
        int unreadCount = messageService.getUnreadCount(
                roomId,
                currentUser.getUserId()
        );
        return ResponseEntity.ok(Map.of("unread_count", unreadCount));
    }

    @DeleteMapping("/{messageId}")
    @Operation(summary = "메시지 삭제")
    public ResponseEntity<Map<String, String>> deleteMessage(
            @CurrentUser JwtPayload currentUser,
            @PathVariable String messageId) {
        messageService.deleteMessage(messageId, currentUser.getUserId());
        return ResponseEntity.ok(Map.of("message", "Message deleted"));
    }

    @PutMapping("/{messageId}")
    @Operation(summary = "메시지 수정")
    public ResponseEntity<MessageResponse> updateMessage(
            @CurrentUser JwtPayload currentUser,
            @PathVariable String messageId,
            @Valid @RequestBody MessageUpdateRequest request) {
        MessageResponse message = messageService.updateMessage(
                messageId,
                currentUser.getUserId(),
                request.getContent()
        );
        return ResponseEntity.ok(message);
    }
}
