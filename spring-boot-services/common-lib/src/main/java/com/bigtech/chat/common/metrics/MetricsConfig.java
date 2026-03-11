package com.bigtech.chat.common.metrics;

import io.micrometer.core.aop.TimedAspect;
import io.micrometer.core.instrument.MeterRegistry;
import io.micrometer.core.instrument.Tag;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.actuate.autoconfigure.metrics.MeterRegistryCustomizer;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import java.util.List;

/**
 * Micrometer 메트릭 설정
 *
 * Prometheus 연동을 위한 기본 설정을 제공합니다.
 */
@Configuration
public class MetricsConfig {

    @Value("${spring.application.name:unknown}")
    private String applicationName;

    /**
     * 모든 메트릭에 공통 태그 추가
     */
    @Bean
    public MeterRegistryCustomizer<MeterRegistry> metricsCommonTags() {
        return registry -> registry.config()
                .commonTags(List.of(
                        Tag.of("application", applicationName)
                ));
    }

    /**
     * @Timed 어노테이션 지원
     */
    @Bean
    public TimedAspect timedAspect(MeterRegistry registry) {
        return new TimedAspect(registry);
    }
}
