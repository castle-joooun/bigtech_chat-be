package com.bigtech.chat.common.cache;

import java.util.Optional;
import java.util.function.Supplier;

/**
 * 캐시 서비스 인터페이스
 */
public interface CacheService {

    int DEFAULT_TTL = 300;   // 5분
    int SHORT_TTL = 60;      // 1분
    int LONG_TTL = 3600;     // 1시간
    int SESSION_TTL = 86400; // 24시간

    /**
     * 캐시 조회
     */
    <T> Optional<T> get(String key, Class<T> type);

    /**
     * 캐시 저장 (기본 TTL)
     */
    void set(String key, Object value);

    /**
     * 캐시 저장 (TTL 지정)
     */
    void set(String key, Object value, int ttlSeconds);

    /**
     * 캐시 삭제
     */
    boolean delete(String key);

    /**
     * 패턴으로 캐시 삭제
     */
    long deletePattern(String pattern);

    /**
     * 캐시 존재 여부 확인
     */
    boolean exists(String key);

    /**
     * Cache-Aside 패턴: 캐시에 없으면 fallback 실행 후 캐싱
     */
    <T> T getOrSet(String key, Supplier<T> fallback, int ttlSeconds, Class<T> type);

    /**
     * Cache-Aside 패턴 (기본 TTL)
     */
    default <T> T getOrSet(String key, Supplier<T> fallback, Class<T> type) {
        return getOrSet(key, fallback, DEFAULT_TTL, type);
    }

    /**
     * 카운터 증가
     */
    Long increment(String key);

    /**
     * 카운터 증가 (증가량 지정)
     */
    Long increment(String key, long delta);

    /**
     * 리스트 앞에 데이터 추가 (LPUSH) + 최대 길이 유지 (LTRIM) + TTL 설정
     */
    long listPush(String key, Object value, int maxLength, int ttlSeconds);

    /**
     * 리스트 범위 조회 (LRANGE)
     */
    <T> java.util.List<T> listRange(String key, int start, int end, Class<T> type);
}
