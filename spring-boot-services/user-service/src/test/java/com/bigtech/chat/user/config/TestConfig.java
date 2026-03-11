package com.bigtech.chat.user.config;

import com.bigtech.chat.common.cache.CacheService;
import com.bigtech.chat.common.kafka.KafkaProducerService;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.data.redis.core.RedisTemplate;

import static org.mockito.Mockito.mock;

/**
 * 테스트용 설정
 * Redis, Kafka 등 외부 의존성을 Mock으로 대체합니다.
 */
@TestConfiguration
public class TestConfig {

    @Bean
    @Primary
    public CacheService cacheService() {
        return mock(CacheService.class);
    }

    @Bean
    @Primary
    public KafkaProducerService kafkaProducerService() {
        return mock(KafkaProducerService.class);
    }

    @Bean
    @Primary
    @SuppressWarnings("unchecked")
    public RedisTemplate<String, String> redisTemplate() {
        return mock(RedisTemplate.class);
    }
}
