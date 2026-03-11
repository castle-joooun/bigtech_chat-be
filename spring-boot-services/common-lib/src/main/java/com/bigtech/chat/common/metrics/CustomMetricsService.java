package com.bigtech.chat.common.metrics;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Timer;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.function.Supplier;

/**
 * 커스텀 메트릭 서비스
 *
 * 비즈니스 메트릭을 쉽게 등록하고 관리할 수 있도록 도와줍니다.
 */
@Service
@Slf4j
public class CustomMetricsService {

    private final MeterRegistry meterRegistry;
    private final ConcurrentHashMap<String, Counter> counters = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, Timer> timers = new ConcurrentHashMap<>();
    private final ConcurrentHashMap<String, AtomicInteger> gaugeValues = new ConcurrentHashMap<>();

    public CustomMetricsService(MeterRegistry meterRegistry) {
        this.meterRegistry = meterRegistry;
    }

    /**
     * 카운터 증가
     */
    public void incrementCounter(String name, String... tags) {
        String key = buildKey(name, tags);
        Counter counter = counters.computeIfAbsent(key, k ->
                Counter.builder(name)
                        .tags(tags)
                        .description("Counter for " + name)
                        .register(meterRegistry)
        );
        counter.increment();
    }

    /**
     * 카운터 특정 값만큼 증가
     */
    public void incrementCounter(String name, double amount, String... tags) {
        String key = buildKey(name, tags);
        Counter counter = counters.computeIfAbsent(key, k ->
                Counter.builder(name)
                        .tags(tags)
                        .description("Counter for " + name)
                        .register(meterRegistry)
        );
        counter.increment(amount);
    }

    /**
     * 타이머 기록
     */
    public Timer.Sample startTimer() {
        return Timer.start(meterRegistry);
    }

    /**
     * 타이머 종료 및 기록
     */
    public void stopTimer(Timer.Sample sample, String name, String... tags) {
        String key = buildKey(name, tags);
        Timer timer = timers.computeIfAbsent(key, k ->
                Timer.builder(name)
                        .tags(tags)
                        .description("Timer for " + name)
                        .register(meterRegistry)
        );
        sample.stop(timer);
    }

    /**
     * 게이지 값 설정
     */
    public void setGauge(String name, int value, String... tags) {
        String key = buildKey(name, tags);
        AtomicInteger atomicValue = gaugeValues.computeIfAbsent(key, k -> {
            AtomicInteger ai = new AtomicInteger(value);
            Gauge.builder(name, ai, AtomicInteger::get)
                    .tags(tags)
                    .description("Gauge for " + name)
                    .register(meterRegistry);
            return ai;
        });
        atomicValue.set(value);
    }

    /**
     * 게이지 등록 (Supplier 기반)
     */
    public <T extends Number> void registerGauge(String name, Supplier<T> valueSupplier, String... tags) {
        Gauge.builder(name, valueSupplier, supplier -> supplier.get().doubleValue())
                .tags(tags)
                .description("Gauge for " + name)
                .register(meterRegistry);
    }

    private String buildKey(String name, String... tags) {
        StringBuilder sb = new StringBuilder(name);
        for (String tag : tags) {
            sb.append(":").append(tag);
        }
        return sb.toString();
    }

    // ========== 비즈니스 메트릭 헬퍼 메서드 ==========

    /**
     * HTTP 요청 카운터
     */
    public void recordHttpRequest(String method, String uri, int status) {
        incrementCounter("http_requests_total",
                "method", method,
                "uri", uri,
                "status", String.valueOf(status));
    }

    /**
     * 메시지 전송 카운터
     */
    public void recordMessageSent(Long roomId) {
        incrementCounter("chat_messages_sent_total",
                "room_id", String.valueOf(roomId));
    }

    /**
     * 사용자 로그인 카운터
     */
    public void recordUserLogin(boolean success) {
        incrementCounter("user_login_total",
                "success", String.valueOf(success));
    }

    /**
     * 친구 요청 카운터
     */
    public void recordFriendRequest(String status) {
        incrementCounter("friend_requests_total",
                "status", status);
    }

    /**
     * WebSocket/SSE 연결 수
     */
    public void setActiveConnections(String type, int count) {
        setGauge("active_connections",
                count,
                "type", type);
    }

    /**
     * Kafka 메시지 발행 카운터
     */
    public void recordKafkaMessagePublished(String topic) {
        incrementCounter("kafka_messages_published_total",
                "topic", topic);
    }

    /**
     * Kafka 메시지 소비 카운터
     */
    public void recordKafkaMessageConsumed(String topic) {
        incrementCounter("kafka_messages_consumed_total",
                "topic", topic);
    }
}
