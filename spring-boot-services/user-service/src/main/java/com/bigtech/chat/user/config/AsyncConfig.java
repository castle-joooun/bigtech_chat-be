package com.bigtech.chat.user.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.scheduling.concurrent.ThreadPoolTaskExecutor;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.concurrent.Executor;
import java.util.concurrent.ThreadPoolExecutor;

/**
 * 비동기 처리 및 트랜잭션 설정 (Java 21 + Virtual Thread 최적화)
 *
 * 아키텍처:
 *   [클라이언트] → [Tomcat Virtual Thread] → [bcryptExecutor Platform Thread] → [응답]
 *
 * Virtual Thread (spring.threads.virtual.enabled=true):
 *   - Tomcat 요청 스레드가 경량 Virtual Thread로 전환
 *   - I/O 대기 시 carrier thread 즉시 해방 → 수백만 동시 요청 처리 가능
 *   - 일반 API (DB 조회, Redis, Kafka)는 Virtual Thread에서 직접 처리
 *
 * BCrypt 전용 Platform Thread 풀 (bcryptExecutor):
 *   - BCrypt는 CPU-bound (~250ms/hash) → Virtual Thread에서 실행하면 carrier thread 점유
 *   - 별도 Platform Thread 풀로 격리하여 다른 Virtual Thread에 영향 없음
 *   - CPU 코어 수 기반 동적 할당으로 하드웨어 최적 활용
 *
 * 핵심: CompletableFuture.supplyAsync() + 컨트롤러 비동기 반환으로 논블로킹 달성
 */
@Configuration
public class AsyncConfig {

    /**
     * BCrypt 전용 Platform Thread 풀
     *
     * CPU 코어 수 기반 동적 할당:
     *   - corePoolSize = CPU 코어 수 (상시 유지)
     *   - maxPoolSize  = CPU 코어 수 × 2 (피크 시 확장)
     *   - queueCapacity = 500 (50+ VU 동시 요청 대응)
     *
     * CallerRunsPolicy: 큐 포화 시 호출 스레드(Virtual Thread)에서 직접 실행
     *   → 요청 드롭 없이 graceful degradation
     *
     * 참고 - FastAPI 비교:
     *   FastAPI는 ThreadPoolExecutor(max_workers=4) 고정
     *   Spring은 CPU 코어에 맞춰 동적 확장 가능 → 이것이 Spring의 동시성 강점
     */
    @Bean("bcryptExecutor")
    public Executor bcryptExecutor() {
        int cpuCores = Runtime.getRuntime().availableProcessors();

        ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
        executor.setCorePoolSize(cpuCores);            // CPU 코어 수 (동적)
        executor.setMaxPoolSize(cpuCores * 2);         // 피크 시 코어 × 2
        executor.setQueueCapacity(500);                // 50+ VU 동시 요청 대응
        executor.setThreadNamePrefix("bcrypt-");
        executor.setRejectedExecutionHandler(new ThreadPoolExecutor.CallerRunsPolicy());
        executor.setWaitForTasksToCompleteOnShutdown(true);
        executor.setAwaitTerminationSeconds(30);
        executor.initialize();
        return executor;
    }

    /**
     * 프로그래밍 방식 트랜잭션 관리
     * CompletableFuture 체인 내에서 트랜잭션 수동 제어 필요
     * (@Transactional은 프록시 기반이라 다른 스레드에서 동작하지 않음)
     */
    @Bean
    public TransactionTemplate transactionTemplate(PlatformTransactionManager transactionManager) {
        return new TransactionTemplate(transactionManager);
    }
}
