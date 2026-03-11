package com.bigtech.chat.common.kafka;

import com.bigtech.chat.common.kafka.events.DomainEvent;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.apache.kafka.clients.producer.ProducerRecord;
import org.apache.kafka.clients.producer.RecordMetadata;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.kafka.support.SendResult;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.concurrent.CompletableFuture;

/**
 * Kafka 이벤트 발행 서비스
 */
@Service
@RequiredArgsConstructor
@Slf4j
public class KafkaProducerService {

    private final KafkaTemplate<String, Map<String, Object>> kafkaTemplate;

    /**
     * 이벤트 발행 (키 없음)
     */
    public <T extends DomainEvent> CompletableFuture<Boolean> publish(String topic, T event) {
        return publish(topic, event, null);
    }

    /**
     * 이벤트 발행 (키 지정)
     */
    public <T extends DomainEvent> CompletableFuture<Boolean> publish(String topic, T event, String key) {
        try {
            Map<String, Object> eventData = event.toMap();
            ProducerRecord<String, Map<String, Object>> record = new ProducerRecord<>(topic, key, eventData);

            return kafkaTemplate.send(record)
                    .thenApply(this::handleSuccess)
                    .exceptionally(this::handleFailure);

        } catch (Exception e) {
            log.error("[Kafka Error] Topic: {}, Error: {}", topic, e.getMessage());
            return CompletableFuture.completedFuture(false);
        }
    }

    /**
     * Map 직접 발행
     */
    public CompletableFuture<Boolean> publishMap(String topic, Map<String, Object> data, String key) {
        try {
            ProducerRecord<String, Map<String, Object>> record = new ProducerRecord<>(topic, key, data);

            return kafkaTemplate.send(record)
                    .thenApply(this::handleSuccess)
                    .exceptionally(this::handleFailure);

        } catch (Exception e) {
            log.error("[Kafka Error] Topic: {}, Error: {}", topic, e.getMessage());
            return CompletableFuture.completedFuture(false);
        }
    }

    private Boolean handleSuccess(SendResult<String, Map<String, Object>> result) {
        RecordMetadata metadata = result.getRecordMetadata();
        log.info("[Event Published] Topic: {}, Partition: {}, Offset: {}",
                metadata.topic(), metadata.partition(), metadata.offset());
        return true;
    }

    private Boolean handleFailure(Throwable ex) {
        log.error("[Kafka Publish Failed] Error: {}", ex.getMessage());
        return false;
    }
}
