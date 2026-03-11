package com.bigtech.chat.chat.controller;

import com.bigtech.chat.chat.dto.ChatRoomResponse;
import com.bigtech.chat.chat.service.ChatRoomService;
import com.bigtech.chat.common.security.CurrentUser;
import com.bigtech.chat.common.security.JwtPayload;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;

/**
 * 채팅방 컨트롤러
 */
@RestController
@RequestMapping("/api/chat-rooms")
@RequiredArgsConstructor
@Tag(name = "Chat Rooms", description = "채팅방 관리 API")
public class ChatRoomController {

    private final ChatRoomService chatRoomService;

    @GetMapping
    @Operation(summary = "채팅방 목록 조회")
    public ResponseEntity<List<ChatRoomResponse>> getChatRooms(
            @CurrentUser JwtPayload currentUser,
            @RequestParam(defaultValue = "0") int skip,
            @RequestParam(defaultValue = "10") int limit) {
        List<ChatRoomResponse> rooms = chatRoomService.getChatRooms(
                currentUser.getUserId(), skip, limit);
        return ResponseEntity.ok(rooms);
    }

    @GetMapping("/check/{targetUserId}")
    @Operation(summary = "채팅방 조회 또는 생성")
    public ResponseEntity<ChatRoomResponse> getOrCreateChatRoom(
            @CurrentUser JwtPayload currentUser,
            @PathVariable Long targetUserId) {
        ChatRoomResponse room = chatRoomService.getOrCreateChatRoom(
                currentUser.getUserId(),
                targetUserId
        );
        return ResponseEntity.ok(room);
    }

    @GetMapping("/{roomId}")
    @Operation(summary = "채팅방 상세 조회")
    public ResponseEntity<ChatRoomResponse> getChatRoomDetail(
            @CurrentUser JwtPayload currentUser,
            @PathVariable Long roomId) {
        ChatRoomResponse room = chatRoomService.getChatRoomDetail(roomId, currentUser.getUserId());
        return ResponseEntity.ok(room);
    }
}
