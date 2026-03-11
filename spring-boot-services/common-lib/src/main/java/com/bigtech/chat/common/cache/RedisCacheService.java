package com.bigtech.chat.common.cache;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.RedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.function.Supplier;

/**
 * Redis 기반 캐시 서비스 구현
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class RedisCacheService implements CacheService {

    private final RedisTemplate<String, String> redisTemplate;
    private final ObjectMapper objectMapper;

    @Override
    public <T> Optional<T> get(String key, Class<T> type) {
        try {
            String value = redisTemplate.opsForValue().get(key);
            if (value == null) {
                return Optional.empty();
            }

            // String 타입은 그대로 반환
            if (type == String.class) {
                return Optional.of(type.cast(value));
            }

            // JSON 파싱
            T result = objectMapper.readValue(value, type);
            return Optional.ofNullable(result);

        } catch (JsonProcessingException e) {
            log.warn("Cache get failed for key '{}': JSON parse error", key);
            return Optional.empty();
        } catch (Exception e) {
            log.warn("Cache get failed for key '{}': {}", key, e.getMessage());
            return Optional.empty();
        }
    }

    @Override
    public void set(String key, Object value) {
        set(key, value, DEFAULT_TTL);
    }

    @Override
    public void set(String key, Object value, int ttlSeconds) {
        try {
            String serialized;
            if (value instanceof String) {
                serialized = (String) value;
            } else {
                serialized = objectMapper.writeValueAsString(value);
            }

            redisTemplate.opsForValue().set(key, serialized, Duration.ofSeconds(ttlSeconds));

        } catch (JsonProcessingException e) {
            log.warn("Cache set failed for key '{}': JSON serialization error", key);
        } catch (Exception e) {
            log.warn("Cache set failed for key '{}': {}", key, e.getMessage());
        }
    }

    @Override
    public boolean delete(String key) {
        try {
            return Boolean.TRUE.equals(redisTemplate.delete(key));
        } catch (Exception e) {
            log.warn("Cache delete failed for key '{}': {}", key, e.getMessage());
            return false;
        }
    }

    @Override
    public long deletePattern(String pattern) {
        try {
            Set<String> keys = redisTemplate.keys(pattern);
            if (keys != null && !keys.isEmpty()) {
                Long deleted = redisTemplate.delete(keys);
                log.info("Deleted {} keys matching pattern '{}'", deleted, pattern);
                return deleted != null ? deleted : 0;
            }
            return 0;
        } catch (Exception e) {
            log.warn("Cache deletePattern failed for '{}': {}", pattern, e.getMessage());
            return 0;
        }
    }

    @Override
    public boolean exists(String key) {
        try {
            return Boolean.TRUE.equals(redisTemplate.hasKey(key));
        } catch (Exception e) {
            log.warn("Cache exists check failed for key '{}': {}", key, e.getMessage());
            return false;
        }
    }

    @Override
    public <T> T getOrSet(String key, Supplier<T> fallback, int ttlSeconds, Class<T> type) {
        // 캐시 조회
        Optional<T> cached = get(key, type);
        if (cached.isPresent()) {
            return cached.get();
        }

        // fallback 실행
        T value = fallback.get();

        // 캐싱
        if (value != null) {
            set(key, value, ttlSeconds);
        }

        return value;
    }

    @Override
    public Long increment(String key) {
        return increment(key, 1);
    }

    @Override
    public Long increment(String key, long delta) {
        try {
            return redisTemplate.opsForValue().increment(key, delta);
        } catch (Exception e) {
            log.warn("Cache increment failed for key '{}': {}", key, e.getMessage());
            return null;
        }
    }

    @Override
    public long listPush(String key, Object value, int maxLength, int ttlSeconds) {
        try {
            String serialized;
            if (value instanceof String) {
                serialized = (String) value;
            } else {
                serialized = objectMapper.writeValueAsString(value);
            }

            // LPUSH: 리스트 앞에 추가
            Long length = redisTemplate.opsForList().leftPush(key, serialized);

            // LTRIM: 최대 길이 유지
            redisTemplate.opsForList().trim(key, 0, maxLength - 1);

            // TTL 설정
            redisTemplate.expire(key, Duration.ofSeconds(ttlSeconds));

            return length != null ? length : 0;
        } catch (JsonProcessingException e) {
            log.warn("Cache listPush failed for key '{}': JSON serialization error", key);
            return 0;
        } catch (Exception e) {
            log.warn("Cache listPush failed for key '{}': {}", key, e.getMessage());
            return 0;
        }
    }

    @Override
    public <T> List<T> listRange(String key, int start, int end, Class<T> type) {
        try {
            List<String> values = redisTemplate.opsForList().range(key, start, end);
            if (values == null || values.isEmpty()) {
                return new ArrayList<>();
            }

            List<T> result = new ArrayList<>();
            for (String v : values) {
                if (type == String.class) {
                    result.add(type.cast(v));
                } else {
                    result.add(objectMapper.readValue(v, type));
                }
            }
            return result;
        } catch (Exception e) {
            log.warn("Cache listRange failed for key '{}': {}", key, e.getMessage());
            return new ArrayList<>();
        }
    }
}
