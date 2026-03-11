package com.bigtech.chat.chat.sse;

import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.io.IOException;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.CopyOnWriteArraySet;

/**
 * SSE Emitter 중앙 관리자
 *
 * 채팅방별로 연결된 클라이언트들을 관리하고 메시지를 브로드캐스트합니다.
 *
 * <h2>데이터 구조</h2>
 * <pre>
 * roomConnections: roomId -> Set&lt;SseConnection&gt;  (채팅방별 연결)
 * userConnections: userId -> Set&lt;SseConnection&gt;  (사용자별 연결, 멀티 디바이스 지원)
 * </pre>
 *
 * <h2>Spring Boot SSE 아키텍처 (FastAPI 대비 장점)</h2>
 * <pre>
 * [Spring Boot - 중앙집중형]
 * - SseEmitterManager가 모든 SSE 연결을 ConcurrentHashMap으로 관리
 * - MessageEventConsumer(@KafkaListener)가 이벤트 수신 후 여기로 브로드캐스트 위임
 * - 메모리 효율적: 1개의 Kafka Consumer가 모든 SSE 연결에 이벤트 분배
 * - 연결 관리: 타임아웃/에러/완료 시 자동 정리 (onTimeout, onError, onCompletion)
 *
 * [FastAPI - 분산형]
 * - 각 SSE 요청마다 독립적인 AIOKafkaConsumer 생성
 * - async generator로 SSE 스트림 구현
 * - 연결당 Kafka Consumer 1개 → 연결 수에 비례하여 리소스 증가
 * </pre>
 */
@Component
@Slf4j
public class SseEmitterManager {

    // roomId -> 해당 방에 연결된 SSE 연결들
    private final Map<Long, Set<SseConnection>> roomConnections = new ConcurrentHashMap<>();

    // userId -> 해당 사용자의 모든 SSE 연결 (여러 탭/기기)
    private final Map<Long, Set<SseConnection>> userConnections = new ConcurrentHashMap<>();

    private static final long SSE_TIMEOUT = 30 * 60 * 1000L; // 30분

    /**
     * SSE 연결 정보
     */
    public record SseConnection(Long userId, Long roomId, SseEmitter emitter) {}

    /**
     * 새 SSE 연결 생성 및 등록
     */
    public SseEmitter createAndRegister(Long userId, Long roomId) {
        SseEmitter emitter = new SseEmitter(SSE_TIMEOUT);
        SseConnection connection = new SseConnection(userId, roomId, emitter);

        // 방별 연결 등록
        roomConnections.computeIfAbsent(roomId, k -> new CopyOnWriteArraySet<>()).add(connection);

        // 사용자별 연결 등록
        userConnections.computeIfAbsent(userId, k -> new CopyOnWriteArraySet<>()).add(connection);

        // 연결 종료 시 정리
        emitter.onCompletion(() -> removeConnection(connection));
        emitter.onTimeout(() -> removeConnection(connection));
        emitter.onError(e -> {
            log.warn("SSE error for user {} in room {}: {}", userId, roomId, e.getMessage());
            removeConnection(connection);
        });

        log.info("SSE connection created: userId={}, roomId={}", userId, roomId);

        // 연결 성공 이벤트 전송
        try {
            emitter.send(SseEmitter.event()
                    .name("connected")
                    .data(Map.of(
                            "message", "Connected to room " + roomId,
                            "room_id", roomId,
                            "user_id", userId
                    )));
        } catch (IOException e) {
            log.error("Failed to send connected event: {}", e.getMessage());
        }

        return emitter;
    }

    /**
     * 특정 채팅방에 메시지 브로드캐스트
     */
    public void broadcastToRoom(Long roomId, String eventName, Object data) {
        Set<SseConnection> connections = roomConnections.get(roomId);
        if (connections == null || connections.isEmpty()) {
            log.debug("No connections for room {}", roomId);
            return;
        }

        log.debug("Broadcasting {} to room {} ({} connections)", eventName, roomId, connections.size());

        for (SseConnection connection : connections) {
            try {
                connection.emitter().send(SseEmitter.event()
                        .name(eventName)
                        .data(data));
            } catch (IOException e) {
                log.warn("Failed to send to user {}: {}", connection.userId(), e.getMessage());
                removeConnection(connection);
            }
        }
    }

    /**
     * 특정 채팅방에서 특정 사용자 제외하고 브로드캐스트 (본인 제외)
     */
    public void broadcastToRoomExcludingUser(Long roomId, Long excludeUserId, String eventName, Object data) {
        Set<SseConnection> connections = roomConnections.get(roomId);
        if (connections == null || connections.isEmpty()) {
            return;
        }

        for (SseConnection connection : connections) {
            if (!connection.userId().equals(excludeUserId)) {
                try {
                    connection.emitter().send(SseEmitter.event()
                            .name(eventName)
                            .data(data));
                } catch (IOException e) {
                    log.warn("Failed to send to user {}: {}", connection.userId(), e.getMessage());
                    removeConnection(connection);
                }
            }
        }
    }

    /**
     * 특정 사용자에게 메시지 전송 (모든 연결된 탭/기기)
     */
    public void sendToUser(Long userId, String eventName, Object data) {
        Set<SseConnection> connections = userConnections.get(userId);
        if (connections == null || connections.isEmpty()) {
            log.debug("No connections for user {}", userId);
            return;
        }

        for (SseConnection connection : connections) {
            try {
                connection.emitter().send(SseEmitter.event()
                        .name(eventName)
                        .data(data));
            } catch (IOException e) {
                log.warn("Failed to send to user {}: {}", userId, e.getMessage());
                removeConnection(connection);
            }
        }
    }

    /**
     * 연결 제거
     */
    private void removeConnection(SseConnection connection) {
        Set<SseConnection> roomConns = roomConnections.get(connection.roomId());
        if (roomConns != null) {
            roomConns.remove(connection);
            if (roomConns.isEmpty()) {
                roomConnections.remove(connection.roomId());
            }
        }

        Set<SseConnection> userConns = userConnections.get(connection.userId());
        if (userConns != null) {
            userConns.remove(connection);
            if (userConns.isEmpty()) {
                userConnections.remove(connection.userId());
            }
        }

        log.info("SSE connection removed: userId={}, roomId={}", connection.userId(), connection.roomId());
    }

    /**
     * 특정 방의 연결 수 조회
     */
    public int getConnectionCount(Long roomId) {
        Set<SseConnection> connections = roomConnections.get(roomId);
        return connections != null ? connections.size() : 0;
    }

    /**
     * 특정 사용자의 연결 수 조회
     */
    public int getUserConnectionCount(Long userId) {
        Set<SseConnection> connections = userConnections.get(userId);
        return connections != null ? connections.size() : 0;
    }

    /**
     * 전체 활성 연결 수
     */
    public int getTotalConnectionCount() {
        return roomConnections.values().stream()
                .mapToInt(Set::size)
                .sum();
    }

    /**
     * SSE 연결 유지용 ping (30초 간격)
     *
     * FastAPI의 EventSourceResponse(ping=30)과 동일한 역할:
     * - 연결이 끊어진 클라이언트를 감지하여 정리
     * - 프록시/로드밸런서의 유휴 타임아웃 방지
     */
    @Scheduled(fixedRate = 30000)
    public void sendPing() {
        int totalConnections = getTotalConnectionCount();
        if (totalConnections == 0) {
            return;
        }

        log.debug("Sending SSE ping to {} connections", totalConnections);

        for (Set<SseConnection> connections : roomConnections.values()) {
            for (SseConnection connection : connections) {
                try {
                    connection.emitter().send(SseEmitter.event()
                            .name("ping")
                            .data(Map.of("timestamp", System.currentTimeMillis())));
                } catch (IOException e) {
                    log.debug("Ping failed for user {}, removing connection", connection.userId());
                    removeConnection(connection);
                }
            }
        }
    }
}
