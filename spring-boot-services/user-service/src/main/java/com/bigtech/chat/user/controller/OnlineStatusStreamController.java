package com.bigtech.chat.user.controller;

import com.bigtech.chat.common.security.CurrentUser;
import com.bigtech.chat.common.security.JwtPayload;
import com.bigtech.chat.user.service.OnlineStatusService;
import com.bigtech.chat.user.sse.OnlineStatusSseManager;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.MediaType;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * 온라인 상태 실시간 스트리밍 컨트롤러 (SSE)
 *
 * Server-Sent Events를 통해 친구들의 온라인 상태 변경을 실시간으로 전달합니다.
 *
 * 사용 방법 (JavaScript):
 * ```javascript
 * const eventSource = new EventSource('/api/online-status/stream', {
 *     headers: { 'Authorization': 'Bearer ' + token }
 * });
 *
 * eventSource.addEventListener('connected', (e) => {
 *     console.log('Connected:', JSON.parse(e.data));
 * });
 *
 * eventSource.addEventListener('initial', (e) => {
 *     const statuses = JSON.parse(e.data);
 *     // 초기 친구들의 온라인 상태
 *     updateFriendStatuses(statuses);
 * });
 *
 * eventSource.addEventListener('status', (e) => {
 *     const { user_id, is_online } = JSON.parse(e.data);
 *     updateFriendStatus(user_id, is_online);
 * });
 * ```
 *
 * 이벤트 종류:
 * - connected: 연결 성공
 * - initial: 초기 친구들의 온라인 상태 목록
 * - status: 친구의 온라인 상태 변경
 */
@RestController
@RequestMapping("/api/online-status")
@RequiredArgsConstructor
@Slf4j
@Tag(name = "Online Status Stream", description = "실시간 온라인 상태 스트리밍 API (SSE)")
public class OnlineStatusStreamController {

    private final OnlineStatusSseManager sseManager;
    private final OnlineStatusService onlineStatusService;

    /**
     * 온라인 상태 실시간 스트리밍 (SSE)
     *
     * 클라이언트는 이 엔드포인트에 연결하여 친구들의 온라인 상태 변경을 실시간으로 수신합니다.
     *
     * @param currentUser 현재 인증된 사용자
     * @return SSE Emitter (실시간 이벤트 스트림)
     */
    @GetMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    @Operation(summary = "온라인 상태 실시간 스트리밍",
            description = "SSE를 통해 친구들의 온라인 상태 변경을 실시간으로 수신합니다.")
    public SseEmitter streamOnlineStatus(@CurrentUser JwtPayload currentUser) {
        Long userId = currentUser.getUserId();

        log.info("Online status SSE stream requested: userId={}", userId);

        // 친구 목록 조회 (실제로는 FriendService 호출)
        Set<Long> friendIds = getFriendIds(userId);

        // SSE 연결 생성 및 등록
        SseEmitter emitter = sseManager.createAndRegister(userId, friendIds);

        // 초기 온라인 상태 전송
        sendInitialStatus(emitter, friendIds);

        return emitter;
    }

    /**
     * 친구 목록 조회 (실제로는 FriendService 또는 API 호출)
     * TODO: FriendService 연동 필요
     */
    private Set<Long> getFriendIds(Long userId) {
        // 실제 구현에서는 FriendService나 friend-service API 호출
        // 여기서는 빈 Set 반환 (연동 후 수정 필요)
        return new HashSet<>();
    }

    /**
     * 초기 온라인 상태 전송
     */
    private void sendInitialStatus(SseEmitter emitter, Set<Long> friendIds) {
        try {
            if (friendIds.isEmpty()) {
                emitter.send(SseEmitter.event()
                        .name("initial")
                        .data(Map.of("statuses", List.of())));
                return;
            }

            // 친구들의 현재 온라인 상태 조회
            List<Map<String, Object>> statuses = friendIds.stream()
                    .map(friendId -> {
                        boolean isOnline = onlineStatusService.isOnline(friendId);
                        return Map.<String, Object>of(
                                "user_id", friendId,
                                "is_online", isOnline
                        );
                    })
                    .toList();

            emitter.send(SseEmitter.event()
                    .name("initial")
                    .data(Map.of("statuses", statuses)));

        } catch (IOException e) {
            log.error("Failed to send initial status: {}", e.getMessage());
        }
    }

    /**
     * 현재 연결 상태 조회 (디버깅/모니터링용)
     */
    @GetMapping("/stream/status")
    @Operation(summary = "SSE 연결 상태 조회", description = "현재 활성 SSE 연결 수를 조회합니다.")
    public Map<String, Object> getStreamStatus() {
        return Map.of(
                "connected_users", sseManager.getConnectedUserCount(),
                "total_connections", sseManager.getTotalConnectionCount()
        );
    }
}
