package com.bigtech.chat.chat.controller;

import com.bigtech.chat.chat.service.ChatRoomService;
import com.bigtech.chat.chat.sse.SseEmitterManager;
import com.bigtech.chat.common.security.CurrentUser;
import com.bigtech.chat.common.security.JwtPayload;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.Map;

/**
 * 메시지 실시간 스트리밍 컨트롤러 (SSE)
 *
 * Server-Sent Events를 통해 클라이언트에게 실시간 메시지를 전달합니다.
 *
 * 사용 방법 (JavaScript):
 * ```javascript
 * const eventSource = new EventSource('/api/messages/stream/123', {
 *     headers: { 'Authorization': 'Bearer ' + token }
 * });
 *
 * eventSource.addEventListener('connected', (e) => {
 *     console.log('Connected:', JSON.parse(e.data));
 * });
 *
 * eventSource.addEventListener('new_message', (e) => {
 *     const message = JSON.parse(e.data);
 *     displayMessage(message);
 * });
 *
 * eventSource.addEventListener('messages_read', (e) => {
 *     const data = JSON.parse(e.data);
 *     markMessagesAsRead(data.message_ids);
 * });
 * ```
 *
 * 이벤트 종류:
 * - connected: 연결 성공
 * - new_message: 새 메시지 수신
 * - messages_read: 메시지 읽음 상태 변경
 * - message_deleted: 메시지 삭제됨
 * - error: 에러 발생
 */
@RestController
@RequestMapping("/api/messages")
@RequiredArgsConstructor
@Slf4j
@Tag(name = "Message Stream", description = "실시간 메시지 스트리밍 API (SSE)")
public class MessageStreamController {

    private final SseEmitterManager sseEmitterManager;
    private final ChatRoomService chatRoomService;

    /**
     * 채팅방 메시지 실시간 스트리밍 (SSE)
     *
     * 클라이언트는 이 엔드포인트에 연결하여 실시간으로 새 메시지를 수신합니다.
     * Kafka Consumer가 메시지 이벤트를 수신하면 이 연결을 통해 클라이언트에 전달됩니다.
     *
     * @param roomId 채팅방 ID
     * @param currentUser 현재 인증된 사용자
     * @return SSE Emitter (실시간 이벤트 스트림)
     */
    @GetMapping(value = "/stream/{roomId}", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    @Operation(summary = "채팅방 메시지 실시간 스트리밍",
            description = "SSE를 통해 해당 채팅방의 새 메시지를 실시간으로 수신합니다.")
    public SseEmitter streamMessages(
            @PathVariable Long roomId,
            @CurrentUser JwtPayload currentUser) {

        // 채팅방 접근 권한 확인
        chatRoomService.validateAccess(roomId, currentUser.getUserId());

        log.info("SSE stream requested: userId={}, roomId={}", currentUser.getUserId(), roomId);

        // SSE 연결 생성 및 등록
        return sseEmitterManager.createAndRegister(currentUser.getUserId(), roomId);
    }

    /**
     * 현재 연결 상태 조회 (디버깅/모니터링용)
     */
    @GetMapping("/stream/status")
    @Operation(summary = "SSE 연결 상태 조회", description = "현재 활성 SSE 연결 수를 조회합니다.")
    public Map<String, Object> getStreamStatus(@CurrentUser JwtPayload currentUser) {
        return Map.of(
                "total_connections", sseEmitterManager.getTotalConnectionCount(),
                "user_connections", sseEmitterManager.getUserConnectionCount(currentUser.getUserId())
        );
    }

    /**
     * 특정 채팅방의 연결 상태 조회
     */
    @GetMapping("/stream/{roomId}/status")
    @Operation(summary = "채팅방 SSE 연결 상태", description = "특정 채팅방의 활성 SSE 연결 수를 조회합니다.")
    public Map<String, Object> getRoomStreamStatus(
            @PathVariable Long roomId,
            @CurrentUser JwtPayload currentUser) {

        chatRoomService.validateAccess(roomId, currentUser.getUserId());

        return Map.of(
                "room_id", roomId,
                "connection_count", sseEmitterManager.getConnectionCount(roomId)
        );
    }
}
