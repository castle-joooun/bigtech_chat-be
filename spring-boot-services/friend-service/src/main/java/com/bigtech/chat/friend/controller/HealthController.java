package com.bigtech.chat.friend.controller;

import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.Map;

/**
 * 헬스 체크 컨트롤러
 */
@RestController
@Tag(name = "Health", description = "서비스 상태 확인")
public class HealthController {

    @GetMapping("/health")
    @Operation(summary = "헬스 체크")
    public ResponseEntity<Map<String, Object>> health() {
        return ResponseEntity.ok(Map.of(
                "status", "healthy",
                "service", "friend-service",
                "timestamp", LocalDateTime.now().toString()
        ));
    }
}
