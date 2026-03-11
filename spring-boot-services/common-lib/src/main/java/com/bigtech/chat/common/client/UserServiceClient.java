package com.bigtech.chat.common.client;

import com.bigtech.chat.common.exception.ExternalServiceException;
import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker;
import io.github.resilience4j.retry.annotation.Retry;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.ParameterizedTypeReference;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;

import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.ConcurrentHashMap;

/**
 * User Service API 클라이언트
 *
 * MSA 원칙에 따라 다른 서비스(friend-service, chat-service)에서
 * User 정보를 조회할 때 user-service API를 호출합니다.
 *
 * 복원력 패턴:
 * - @CircuitBreaker: user-service 장애 시 빠른 실패 (연쇄 장애 방지)
 * - @Retry: 일시적 오류 시 Exponential Backoff로 자동 재시도
 * - 인메모리 캐싱 (TTL 5분): API 호출 오버헤드 최소화
 */
@Component
@Slf4j
public class UserServiceClient {

    private static final String SERVICE_NAME = "user-service";

    private final RestTemplate restTemplate;
    private final String userServiceUrl;

    // 간단한 인메모리 캐시 (TTL 5분)
    private final Map<Long, CacheEntry<UserProfile>> userCache = new ConcurrentHashMap<>();
    private static final long CACHE_TTL_MS = 5 * 60 * 1000; // 5분

    public UserServiceClient(
            RestTemplate restTemplate,
            @Value("${services.user-service.url:http://localhost:8081}") String userServiceUrl) {
        this.restTemplate = restTemplate;
        this.userServiceUrl = userServiceUrl;
    }

    /**
     * 사용자 ID로 단일 사용자 조회
     *
     * @CircuitBreaker: 실패율 50% 초과 시 OPEN → 60초 후 HALF_OPEN → 3번 성공 시 CLOSED
     * @Retry: 최대 3번 재시도, Exponential Backoff (1초 → 2초 → 4초)
     *
     * @param userId 사용자 ID
     * @return UserProfile 또는 empty
     */
    @CircuitBreaker(name = SERVICE_NAME, fallbackMethod = "getUserByIdFallback")
    @Retry(name = SERVICE_NAME)
    public Optional<UserProfile> getUserById(Long userId) {
        // 캐시 확인
        CacheEntry<UserProfile> cached = userCache.get(userId);
        if (cached != null && !cached.isExpired()) {
            return Optional.ofNullable(cached.getValue());
        }

        try {
            String url = userServiceUrl + "/api/users/" + userId;
            ResponseEntity<UserProfile> response = restTemplate.getForEntity(url, UserProfile.class);

            if (response.getStatusCode().is2xxSuccessful() && response.getBody() != null) {
                UserProfile user = response.getBody();
                userCache.put(userId, new CacheEntry<>(user));
                return Optional.of(user);
            }
        } catch (RestClientException e) {
            log.error("Failed to get user {}: {}", userId, e.getMessage());
            throw new ExternalServiceException("user-service", e);
        }

        return Optional.empty();
    }

    /**
     * 여러 사용자 ID로 일괄 조회
     *
     * @param userIds 사용자 ID 목록
     * @return UserProfile 목록
     */
    @CircuitBreaker(name = SERVICE_NAME, fallbackMethod = "getUsersByIdsFallback")
    @Retry(name = SERVICE_NAME)
    public List<UserProfile> getUsersByIds(List<Long> userIds) {
        if (userIds == null || userIds.isEmpty()) {
            return Collections.emptyList();
        }

        try {
            String url = userServiceUrl + "/api/users/batch";
            UserBatchRequest request = UserBatchRequest.of(userIds);

            ResponseEntity<List<UserProfile>> response = restTemplate.exchange(
                    url,
                    HttpMethod.POST,
                    new org.springframework.http.HttpEntity<>(request),
                    new ParameterizedTypeReference<List<UserProfile>>() {}
            );

            if (response.getStatusCode().is2xxSuccessful() && response.getBody() != null) {
                List<UserProfile> users = response.getBody();

                // 캐시 업데이트
                for (UserProfile user : users) {
                    userCache.put(user.getId(), new CacheEntry<>(user));
                }

                return users;
            }
        } catch (RestClientException e) {
            log.error("Failed to get users by ids {}: {}", userIds, e.getMessage());
            throw new ExternalServiceException("user-service", e);
        }

        return Collections.emptyList();
    }

    /**
     * 사용자 존재 여부 확인
     *
     * @param userId 사용자 ID
     * @return 존재 여부
     */
    @CircuitBreaker(name = SERVICE_NAME, fallbackMethod = "userExistsFallback")
    @Retry(name = SERVICE_NAME)
    public boolean userExists(Long userId) {
        try {
            String url = userServiceUrl + "/api/users/" + userId + "/exists";
            ResponseEntity<UserExistsResponse> response = restTemplate.getForEntity(
                    url, UserExistsResponse.class);

            if (response.getStatusCode().is2xxSuccessful() && response.getBody() != null) {
                return Boolean.TRUE.equals(response.getBody().getExists());
            }
        } catch (RestClientException e) {
            log.error("Failed to check user existence {}: {}", userId, e.getMessage());
            throw new ExternalServiceException("user-service", e);
        }

        return false;
    }

    // =========================================================================
    // Fallback Methods (Circuit Breaker OPEN 시 실행)
    // =========================================================================

    private Optional<UserProfile> getUserByIdFallback(Long userId, Exception e) {
        log.warn("Circuit Breaker OPEN - getUserById fallback for user {}: {}", userId, e.getMessage());

        // 캐시에 있으면 stale 데이터라도 반환 (graceful degradation)
        CacheEntry<UserProfile> cached = userCache.get(userId);
        if (cached != null) {
            log.info("Returning stale cache for user {}", userId);
            return Optional.ofNullable(cached.getValue());
        }

        throw new ExternalServiceException("user-service is temporarily unavailable", e);
    }

    private List<UserProfile> getUsersByIdsFallback(List<Long> userIds, Exception e) {
        log.warn("Circuit Breaker OPEN - getUsersByIds fallback: {}", e.getMessage());
        throw new ExternalServiceException("user-service is temporarily unavailable", e);
    }

    private boolean userExistsFallback(Long userId, Exception e) {
        log.warn("Circuit Breaker OPEN - userExists fallback for user {}: {}", userId, e.getMessage());
        throw new ExternalServiceException("user-service is temporarily unavailable", e);
    }

    // =========================================================================
    // Cache Management
    // =========================================================================

    /**
     * 캐시 무효화
     */
    public void invalidateCache(Long userId) {
        userCache.remove(userId);
    }

    /**
     * 전체 캐시 클리어
     */
    public void clearCache() {
        userCache.clear();
    }

    /**
     * 간단한 캐시 엔트리
     */
    private static class CacheEntry<T> {
        private final T value;
        private final long createdAt;

        CacheEntry(T value) {
            this.value = value;
            this.createdAt = System.currentTimeMillis();
        }

        T getValue() {
            return value;
        }

        boolean isExpired() {
            return System.currentTimeMillis() - createdAt > CACHE_TTL_MS;
        }
    }
}
