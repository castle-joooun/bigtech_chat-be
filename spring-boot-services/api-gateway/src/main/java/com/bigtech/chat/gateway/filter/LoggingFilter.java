package com.bigtech.chat.gateway.filter;

import lombok.extern.slf4j.Slf4j;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

/**
 * 요청/응답 로깅 필터
 */
@Component
@Slf4j
public class LoggingFilter implements GlobalFilter, Ordered {

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        ServerHttpRequest request = exchange.getRequest();
        long startTime = System.currentTimeMillis();

        String requestId = request.getHeaders().getFirst("X-Request-ID");
        String method = request.getMethod().name();
        String path = request.getPath().value();
        String clientIp = request.getRemoteAddress() != null ?
                request.getRemoteAddress().getAddress().getHostAddress() : "unknown";

        log.info("[{}] Request: {} {} from {}", requestId, method, path, clientIp);

        return chain.filter(exchange)
                .then(Mono.fromRunnable(() -> {
                    ServerHttpResponse response = exchange.getResponse();
                    long duration = System.currentTimeMillis() - startTime;
                    int statusCode = response.getStatusCode() != null ?
                            response.getStatusCode().value() : 0;

                    log.info("[{}] Response: {} {} - {} ({}ms)",
                            requestId, method, path, statusCode, duration);
                }));
    }

    @Override
    public int getOrder() {
        return -150;  // RequestIdFilter 이후, JwtFilter 이전
    }
}
