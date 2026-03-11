package com.bigtech.chat.common.security;

import io.jsonwebtoken.*;
import io.jsonwebtoken.security.Keys;
import jakarta.annotation.PostConstruct;
import lombok.Getter;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import javax.crypto.SecretKey;
import java.nio.charset.StandardCharsets;
import java.util.Date;

/**
 * JWT 토큰 생성 및 검증
 *
 * JWT 구조:
 * {
 *   "sub": "user_id",
 *   "email": "user@example.com",
 *   "username": "username",
 *   "type": "access",
 *   "exp": 1234567890
 * }
 */
@Component
@Slf4j
public class JwtTokenProvider {

    @Value("${jwt.secret-key:your-256-bit-secret-key-here-for-hs256-algorithm}")
    private String secretKey;

    @Value("${jwt.access-token-expire-hours:24}")
    @Getter
    private int accessTokenExpireHours;

    private SecretKey key;

    @PostConstruct
    public void init() {
        this.key = Keys.hmacShaKeyFor(secretKey.getBytes(StandardCharsets.UTF_8));
    }

    /**
     * Access Token 생성
     */
    public String createAccessToken(Long userId, String email, String username) {
        Date now = new Date();
        Date expiration = new Date(now.getTime() + (accessTokenExpireHours * 60L * 60L * 1000L));

        return Jwts.builder()
                .subject(String.valueOf(userId))
                .claim("email", email)
                .claim("username", username)
                .claim("type", "access")
                .issuedAt(now)
                .expiration(expiration)
                .signWith(key)
                .compact();
    }

    /**
     * 토큰 파싱 및 검증
     */
    public JwtPayload parseToken(String token) {
        try {
            Claims claims = Jwts.parser()
                    .verifyWith(key)
                    .build()
                    .parseSignedClaims(token)
                    .getPayload();

            if (!"access".equals(claims.get("type", String.class))) {
                log.warn("Invalid token type");
                return null;
            }

            return JwtPayload.builder()
                    .userId(Long.parseLong(claims.getSubject()))
                    .email(claims.get("email", String.class))
                    .username(claims.get("username", String.class))
                    .expiration(claims.getExpiration())
                    .build();

        } catch (ExpiredJwtException e) {
            log.warn("Token expired: {}", e.getMessage());
            return null;
        } catch (JwtException | IllegalArgumentException e) {
            log.warn("Invalid token: {}", e.getMessage());
            return null;
        }
    }

    /**
     * 토큰 유효성 검증
     */
    public boolean validateToken(String token) {
        return parseToken(token) != null;
    }

    /**
     * 만료 시간(초) 반환
     */
    public int getExpirationSeconds() {
        return accessTokenExpireHours * 60 * 60;
    }
}
