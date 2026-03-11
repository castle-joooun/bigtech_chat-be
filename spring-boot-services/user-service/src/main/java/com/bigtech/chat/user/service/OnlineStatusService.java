package com.bigtech.chat.user.service;

import com.bigtech.chat.common.cache.CacheService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

/**
 * 온라인 상태 관리 서비스
 *
 * Redis를 사용하여 사용자의 온라인 상태를 관리합니다.
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class OnlineStatusService {

    private final CacheService cacheService;

    private static final String ONLINE_KEY_PREFIX = "user:online:";
    private static final int ONLINE_TTL = 300; // 5분

    /**
     * 온라인 상태 설정
     */
    public void setOnline(Long userId) {
        String key = ONLINE_KEY_PREFIX + userId;
        cacheService.set(key, "1", ONLINE_TTL);
        log.debug("User {} is now online", userId);
    }

    /**
     * 오프라인 상태 설정
     */
    public void setOffline(Long userId) {
        String key = ONLINE_KEY_PREFIX + userId;
        cacheService.delete(key);
        log.debug("User {} is now offline", userId);
    }

    /**
     * 온라인 상태 확인
     */
    public boolean isOnline(Long userId) {
        String key = ONLINE_KEY_PREFIX + userId;
        return cacheService.exists(key);
    }

    /**
     * Heartbeat 갱신
     */
    public void heartbeat(Long userId) {
        String key = ONLINE_KEY_PREFIX + userId;
        if (cacheService.exists(key)) {
            cacheService.set(key, "1", ONLINE_TTL);
            log.debug("Heartbeat for user {}", userId);
        }
    }
}
