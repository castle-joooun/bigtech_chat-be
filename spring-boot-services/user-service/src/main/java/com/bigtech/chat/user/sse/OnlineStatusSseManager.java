package com.bigtech.chat.user.sse;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArraySet;

/**
 * 온라인 상태 SSE 관리자
 *
 * 사용자별로 연결된 클라이언트들을 관리하고 친구의 온라인 상태 변경을 브로드캐스트합니다.
 *
 * 구조:
 * - userId -> Set<SseEmitter> (여러 탭/기기에서 연결 가능)
 * - friendsMap: userId -> Set<Long> (해당 사용자의 친구 ID 목록)
 */
@Component
@Slf4j
public class OnlineStatusSseManager {

    // userId -> 해당 사용자의 SSE 연결들
    private final Map<Long, Set<SseEmitter>> userEmitters = new ConcurrentHashMap<>();

    // userId -> 해당 사용자의 친구 ID 목록 (캐시)
    private final Map<Long, Set<Long>> friendsCache = new ConcurrentHashMap<>();

    private static final long SSE_TIMEOUT = 30 * 60 * 1000L; // 30분

    /**
     * 새 SSE 연결 생성 및 등록
     *
     * @param userId 사용자 ID
     * @param friendIds 해당 사용자의 친구 ID 목록
     * @return SSE Emitter
     */
    public SseEmitter createAndRegister(Long userId, Set<Long> friendIds) {
        SseEmitter emitter = new SseEmitter(SSE_TIMEOUT);

        // 사용자의 연결 목록에 추가
        userEmitters.computeIfAbsent(userId, k -> new CopyOnWriteArraySet<>()).add(emitter);

        // 친구 목록 캐시
        friendsCache.put(userId, friendIds);

        // 연결 종료 시 정리
        emitter.onCompletion(() -> removeEmitter(userId, emitter));
        emitter.onTimeout(() -> removeEmitter(userId, emitter));
        emitter.onError(e -> {
            log.warn("SSE error for user {}: {}", userId, e.getMessage());
            removeEmitter(userId, emitter);
        });

        log.info("Online status SSE connection created: userId={}", userId);

        // 연결 성공 이벤트 전송
        try {
            emitter.send(SseEmitter.event()
                    .name("connected")
                    .data(Map.of(
                            "message", "Connected to online status stream",
                            "user_id", userId
                    )));
        } catch (IOException e) {
            log.error("Failed to send connected event: {}", e.getMessage());
        }

        return emitter;
    }

    /**
     * 온라인 상태 변경을 관심 있는 사용자들에게 브로드캐스트
     *
     * @param userId 상태가 변경된 사용자 ID
     * @param isOnline 온라인 여부
     */
    public void broadcastStatusChange(Long userId, Boolean isOnline) {
        Map<String, Object> statusData = Map.of(
                "user_id", userId,
                "is_online", isOnline,
                "timestamp", System.currentTimeMillis()
        );

        // userId를 친구로 가진 모든 사용자에게 브로드캐스트
        for (Map.Entry<Long, Set<Long>> entry : friendsCache.entrySet()) {
            Long subscriberId = entry.getKey();
            Set<Long> friends = entry.getValue();

            // 해당 사용자가 변경된 userId를 친구로 가지고 있는 경우
            if (friends.contains(userId)) {
                sendToUser(subscriberId, "status", statusData);
            }
        }

        log.debug("Broadcasted status change: userId={}, isOnline={}", userId, isOnline);
    }

    /**
     * 특정 사용자에게 이벤트 전송
     */
    public void sendToUser(Long userId, String eventName, Object data) {
        Set<SseEmitter> emitters = userEmitters.get(userId);
        if (emitters == null || emitters.isEmpty()) {
            return;
        }

        for (SseEmitter emitter : emitters) {
            try {
                emitter.send(SseEmitter.event()
                        .name(eventName)
                        .data(data));
            } catch (IOException e) {
                log.warn("Failed to send to user {}: {}", userId, e.getMessage());
                removeEmitter(userId, emitter);
            }
        }
    }

    /**
     * 친구 목록 캐시 업데이트
     */
    public void updateFriendsCache(Long userId, Set<Long> friendIds) {
        friendsCache.put(userId, friendIds);
    }

    /**
     * Emitter 제거
     */
    private void removeEmitter(Long userId, SseEmitter emitter) {
        Set<SseEmitter> emitters = userEmitters.get(userId);
        if (emitters != null) {
            emitters.remove(emitter);
            if (emitters.isEmpty()) {
                userEmitters.remove(userId);
                friendsCache.remove(userId);
            }
        }
        log.info("Online status SSE connection removed: userId={}", userId);
    }

    /**
     * 연결된 사용자 수
     */
    public int getConnectedUserCount() {
        return userEmitters.size();
    }

    /**
     * 전체 연결 수
     */
    public int getTotalConnectionCount() {
        return userEmitters.values().stream()
                .mapToInt(Set::size)
                .sum();
    }
}
