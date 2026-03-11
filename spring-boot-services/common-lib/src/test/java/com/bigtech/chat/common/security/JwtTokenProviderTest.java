package com.bigtech.chat.common.security;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import static org.assertj.core.api.Assertions.assertThat;

/**
 * JwtTokenProvider Unit Test
 */
@DisplayName("JwtTokenProvider Unit Test")
class JwtTokenProviderTest {

    private JwtTokenProvider jwtTokenProvider;

    private static final String SECRET_KEY = "your-256-bit-secret-key-here-for-hs256-algorithm-test";
    private static final int EXPIRE_HOURS = 24;

    @BeforeEach
    void setUp() {
        jwtTokenProvider = new JwtTokenProvider();
        ReflectionTestUtils.setField(jwtTokenProvider, "secretKey", SECRET_KEY);
        ReflectionTestUtils.setField(jwtTokenProvider, "accessTokenExpireHours", EXPIRE_HOURS);
        jwtTokenProvider.init();
    }

    @Test
    @DisplayName("Access Token 생성 성공")
    void generateToken_success() {
        // given
        Long userId = 1L;
        String email = "test@example.com";
        String username = "testuser";

        // when
        String token = jwtTokenProvider.createAccessToken(userId, email, username);

        // then
        assertThat(token).isNotNull();
        assertThat(token).isNotEmpty();
        assertThat(token.split("\\.")).hasSize(3); // JWT는 3개의 파트로 구성
    }

    @Test
    @DisplayName("Token 파싱 성공")
    void parseToken_success() {
        // given
        Long userId = 1L;
        String email = "test@example.com";
        String username = "testuser";
        String token = jwtTokenProvider.createAccessToken(userId, email, username);

        // when
        JwtPayload payload = jwtTokenProvider.parseToken(token);

        // then
        assertThat(payload).isNotNull();
        assertThat(payload.getUserId()).isEqualTo(userId);
        assertThat(payload.getEmail()).isEqualTo(email);
        assertThat(payload.getUsername()).isEqualTo(username);
        assertThat(payload.isExpired()).isFalse();
    }

    @Test
    @DisplayName("유효한 Token 검증 성공")
    void validateToken_success() {
        // given
        String token = jwtTokenProvider.createAccessToken(1L, "test@example.com", "testuser");

        // when
        boolean isValid = jwtTokenProvider.validateToken(token);

        // then
        assertThat(isValid).isTrue();
    }

    @Test
    @DisplayName("잘못된 Token 검증 실패")
    void validateToken_invalidToken() {
        // given
        String invalidToken = "invalid.token.here";

        // when
        boolean isValid = jwtTokenProvider.validateToken(invalidToken);

        // then
        assertThat(isValid).isFalse();
    }

    @Test
    @DisplayName("빈 Token 검증 실패")
    void validateToken_emptyToken() {
        // when
        boolean isValid = jwtTokenProvider.validateToken("");

        // then
        assertThat(isValid).isFalse();
    }

    @Test
    @DisplayName("만료 시간(초) 반환")
    void getExpirationSeconds_success() {
        // when
        int seconds = jwtTokenProvider.getExpirationSeconds();

        // then
        assertThat(seconds).isEqualTo(EXPIRE_HOURS * 60 * 60);
    }

    @Test
    @DisplayName("다른 Secret Key로 서명된 Token 검증 실패")
    void parseToken_wrongSecretKey() {
        // given
        String token = jwtTokenProvider.createAccessToken(1L, "test@example.com", "testuser");

        // 다른 secret key로 새로운 provider 생성
        JwtTokenProvider anotherProvider = new JwtTokenProvider();
        ReflectionTestUtils.setField(anotherProvider, "secretKey",
                "different-256-bit-secret-key-here-for-hs256-test");
        ReflectionTestUtils.setField(anotherProvider, "accessTokenExpireHours", EXPIRE_HOURS);
        anotherProvider.init();

        // when
        JwtPayload payload = anotherProvider.parseToken(token);

        // then
        assertThat(payload).isNull();
    }

    @Test
    @DisplayName("만료된 Token 처리")
    void parseToken_expired() {
        // given - 만료 시간을 0으로 설정
        JwtTokenProvider expiredProvider = new JwtTokenProvider();
        ReflectionTestUtils.setField(expiredProvider, "secretKey", SECRET_KEY);
        ReflectionTestUtils.setField(expiredProvider, "accessTokenExpireHours", 0);
        expiredProvider.init();

        String token = expiredProvider.createAccessToken(1L, "test@example.com", "testuser");

        // when - 토큰이 즉시 만료되므로 파싱 실패
        JwtPayload payload = jwtTokenProvider.parseToken(token);

        // then
        // 만료 시간이 0이면 생성 즉시 만료되어 파싱 시 null 반환
        // Note: 실제로는 약간의 시간 차이가 있을 수 있음
        assertThat(payload).isNull();
    }
}
