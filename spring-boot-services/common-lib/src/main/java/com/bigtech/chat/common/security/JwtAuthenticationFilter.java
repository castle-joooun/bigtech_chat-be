package com.bigtech.chat.common.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.Collections;
import java.util.List;
import java.util.Map;

/**
 * JWT 인증 필터
 *
 * 인증 흐름:
 * 1. Authorization 헤더에서 Bearer 토큰 추출
 * 2. 토큰 검증
 * 3. SecurityContext에 인증 정보 설정
 */
@Component
@RequiredArgsConstructor
@Slf4j
public class JwtAuthenticationFilter extends OncePerRequestFilter {

    private final JwtTokenProvider jwtTokenProvider;
    private final ObjectMapper objectMapper;

    private static final List<String> PUBLIC_PATHS = List.of(
            "/health",
            "/actuator",
            "/docs",
            "/swagger-ui",
            "/v3/api-docs",
            "/api/auth/login",
            "/api/auth/register",
            "/api/auth/refresh",
            "/api/users/batch",
            "/internal"
    );

    // 패턴 매칭이 필요한 공개 경로 (정규식)
    private static final List<String> PUBLIC_PATH_PATTERNS = List.of(
            "/api/users/\\d+/exists",   // 사용자 존재 확인 (서비스 간 통신용)
            "/api/users/\\d+"           // 사용자 프로필 조회 (서비스 간 통신용)
    );

    @Override
    protected void doFilterInternal(
            HttpServletRequest request,
            HttpServletResponse response,
            FilterChain filterChain) throws ServletException, IOException {

        String path = request.getRequestURI();

        // 공개 경로는 인증 생략
        if (isPublicPath(path)) {
            filterChain.doFilter(request, response);
            return;
        }

        // Authorization 헤더에서 토큰 추출
        String authHeader = request.getHeader("Authorization");

        // Gateway에서 전달된 사용자 정보 확인
        String userIdHeader = request.getHeader("X-User-ID");
        String userAuthenticatedHeader = request.getHeader("X-User-Authenticated");

        // Gateway에서 인증된 요청 처리
        if ("true".equals(userAuthenticatedHeader) && userIdHeader != null) {
            try {
                Long userId = Long.parseLong(userIdHeader);
                String email = request.getHeader("X-User-Email");
                String username = request.getHeader("X-User-Username");

                JwtPayload payload = JwtPayload.builder()
                        .userId(userId)
                        .email(email)
                        .username(username)
                        .build();

                setAuthentication(payload);
                filterChain.doFilter(request, response);
                return;
            } catch (NumberFormatException e) {
                log.warn("Invalid X-User-ID header: {}", userIdHeader);
            }
        }

        // 직접 JWT 토큰 검증
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            sendUnauthorized(response, "Missing authentication token");
            return;
        }

        String token = authHeader.substring(7);
        JwtPayload payload = jwtTokenProvider.parseToken(token);

        if (payload == null) {
            sendUnauthorized(response, "Invalid or expired token");
            return;
        }

        setAuthentication(payload);
        filterChain.doFilter(request, response);
    }

    private boolean isPublicPath(String path) {
        // 고정 경로 체크
        boolean isFixedPublic = PUBLIC_PATHS.stream().anyMatch(p ->
                path.equals(p) || path.startsWith(p + "/") || path.startsWith(p + ".")
        );
        if (isFixedPublic) {
            return true;
        }

        // 패턴 매칭 체크
        return PUBLIC_PATH_PATTERNS.stream().anyMatch(pattern ->
                path.matches(pattern)
        );
    }

    private void setAuthentication(JwtPayload payload) {
        UsernamePasswordAuthenticationToken authentication =
                new UsernamePasswordAuthenticationToken(payload, null, Collections.emptyList());
        SecurityContextHolder.getContext().setAuthentication(authentication);
    }

    private void sendUnauthorized(HttpServletResponse response, String message) throws IOException {
        response.setStatus(HttpServletResponse.SC_UNAUTHORIZED);
        response.setContentType("application/json;charset=UTF-8");

        Map<String, String> errorResponse = Map.of(
                "error", "unauthorized",
                "message", message
        );

        response.getWriter().write(objectMapper.writeValueAsString(errorResponse));
    }
}
