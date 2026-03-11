package com.bigtech.chat.user.service;

import com.bigtech.chat.common.exception.ConflictException;
import com.bigtech.chat.common.exception.ErrorCode;
import com.bigtech.chat.common.exception.UnauthorizedException;
import com.bigtech.chat.common.kafka.KafkaProducerService;
import com.bigtech.chat.common.security.JwtTokenProvider;
import com.bigtech.chat.user.dto.TokenResponse;
import com.bigtech.chat.user.dto.UserCreateRequest;
import com.bigtech.chat.user.dto.UserLoginRequest;
import com.bigtech.chat.user.entity.User;
import com.bigtech.chat.user.repository.UserRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.test.util.ReflectionTestUtils;
import org.springframework.transaction.support.TransactionCallback;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;
import java.util.concurrent.Executors;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.*;

/**
 * AuthService Unit Test
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("AuthService Unit Test")
class AuthServiceTest {

    @Mock
    private UserRepository userRepository;

    @Mock
    private PasswordEncoder passwordEncoder;

    @Mock
    private JwtTokenProvider jwtTokenProvider;

    @Mock
    private OnlineStatusService onlineStatusService;

    @Mock
    private KafkaProducerService kafkaProducerService;

    @Mock
    private TransactionTemplate transactionTemplate;

    private Executor bcryptExecutor;

    private AuthService authService;

    @BeforeEach
    void setUp() {
        bcryptExecutor = Executors.newSingleThreadExecutor();
        authService = new AuthService(
                userRepository,
                passwordEncoder,
                jwtTokenProvider,
                onlineStatusService,
                kafkaProducerService,
                transactionTemplate,
                bcryptExecutor
        );
        ReflectionTestUtils.setField(authService, "userEventsTopic", "user.events");
        ReflectionTestUtils.setField(authService, "userOnlineStatusTopic", "user.online_status");
    }

    @Nested
    @DisplayName("회원가입 테스트")
    class RegisterTest {

        @Test
        @DisplayName("회원가입 성공")
        void register_success() throws Exception {
            // given
            UserCreateRequest request = UserCreateRequest.builder()
                    .email("test@example.com")
                    .username("testuser")
                    .password("Test1234!")
                    .displayName("Test User")
                    .build();

            User savedUser = User.builder()
                    .id(1L)
                    .email(request.getEmail())
                    .username(request.getUsername())
                    .passwordHash("encodedPassword")
                    .displayName(request.getDisplayName())
                    .build();

            given(userRepository.existsByEmail(request.getEmail())).willReturn(false);
            given(userRepository.existsByUsername(request.getUsername())).willReturn(false);
            given(passwordEncoder.encode(request.getPassword())).willReturn("encodedPassword");
            given(transactionTemplate.execute(any())).willReturn(savedUser);

            // when
            CompletableFuture<User> future = authService.registerAsync(request);
            User result = future.get();

            // then
            assertThat(result).isNotNull();
            assertThat(result.getId()).isEqualTo(1L);
            assertThat(result.getEmail()).isEqualTo(request.getEmail());
            assertThat(result.getUsername()).isEqualTo(request.getUsername());

            verify(userRepository).existsByEmail(request.getEmail());
            verify(userRepository).existsByUsername(request.getUsername());
        }

        @Test
        @DisplayName("회원가입 실패 - 중복 이메일")
        void register_fail_duplicateEmail() {
            // given
            UserCreateRequest request = UserCreateRequest.builder()
                    .email("existing@example.com")
                    .username("newuser")
                    .password("Test1234!")
                    .build();

            given(userRepository.existsByEmail(request.getEmail())).willReturn(true);

            // when & then
            assertThatThrownBy(() -> authService.registerAsync(request))
                    .isInstanceOf(ConflictException.class)
                    .satisfies(ex -> {
                        ConflictException ce = (ConflictException) ex;
                        assertThat(ce.getErrorCode()).isEqualTo(ErrorCode.EMAIL_ALREADY_EXISTS);
                    });

            verify(userRepository).existsByEmail(request.getEmail());
            verify(transactionTemplate, never()).execute(any());
        }

        @Test
        @DisplayName("회원가입 실패 - 중복 사용자명")
        void register_fail_duplicateUsername() {
            // given
            UserCreateRequest request = UserCreateRequest.builder()
                    .email("new@example.com")
                    .username("existinguser")
                    .password("Test1234!")
                    .build();

            given(userRepository.existsByEmail(request.getEmail())).willReturn(false);
            given(userRepository.existsByUsername(request.getUsername())).willReturn(true);

            // when & then
            assertThatThrownBy(() -> authService.registerAsync(request))
                    .isInstanceOf(ConflictException.class)
                    .satisfies(ex -> {
                        ConflictException ce = (ConflictException) ex;
                        assertThat(ce.getErrorCode()).isEqualTo(ErrorCode.USERNAME_ALREADY_EXISTS);
                    });

            verify(userRepository).existsByEmail(request.getEmail());
            verify(userRepository).existsByUsername(request.getUsername());
            verify(transactionTemplate, never()).execute(any());
        }

        @Test
        @DisplayName("회원가입 시 displayName이 없으면 username 사용")
        void register_withoutDisplayName() throws Exception {
            // given
            UserCreateRequest request = UserCreateRequest.builder()
                    .email("test@example.com")
                    .username("testuser")
                    .password("Test1234!")
                    .displayName(null)
                    .build();

            User savedUser = User.builder()
                    .id(1L)
                    .email(request.getEmail())
                    .username(request.getUsername())
                    .passwordHash("encodedPassword")
                    .displayName(request.getUsername()) // username이 displayName으로 사용됨
                    .build();

            given(userRepository.existsByEmail(anyString())).willReturn(false);
            given(userRepository.existsByUsername(anyString())).willReturn(false);
            given(passwordEncoder.encode(anyString())).willReturn("encodedPassword");
            given(transactionTemplate.execute(any())).willReturn(savedUser);

            // when
            CompletableFuture<User> future = authService.registerAsync(request);
            User result = future.get();

            // then
            assertThat(result.getDisplayName()).isEqualTo(request.getUsername());
        }
    }

    @Nested
    @DisplayName("로그인 테스트")
    class LoginTest {

        @Test
        @DisplayName("로그인 성공")
        void login_success() throws Exception {
            // given
            UserLoginRequest request = UserLoginRequest.builder()
                    .email("test@example.com")
                    .password("Test1234!")
                    .build();

            User user = User.builder()
                    .id(1L)
                    .email(request.getEmail())
                    .username("testuser")
                    .passwordHash("encodedPassword")
                    .isActive(true)
                    .isOnline(false)
                    .build();

            given(userRepository.findByEmail(request.getEmail())).willReturn(Optional.of(user));
            given(passwordEncoder.matches(request.getPassword(), user.getPasswordHash())).willReturn(true);
            given(jwtTokenProvider.createAccessToken(user.getId(), user.getEmail(), user.getUsername()))
                    .willReturn("jwt.token.here");
            given(jwtTokenProvider.getExpirationSeconds()).willReturn(86400);
            doNothing().when(transactionTemplate).executeWithoutResult(any());

            // when
            CompletableFuture<TokenResponse> future = authService.loginAsync(request);
            TokenResponse result = future.get();

            // then
            assertThat(result).isNotNull();
            assertThat(result.getAccessToken()).isEqualTo("jwt.token.here");
            assertThat(result.getExpiresIn()).isEqualTo(86400);

            verify(onlineStatusService).setOnline(user.getId());
        }

        @Test
        @DisplayName("로그인 실패 - 존재하지 않는 사용자")
        void login_fail_userNotFound() {
            // given
            UserLoginRequest request = UserLoginRequest.builder()
                    .email("notexist@example.com")
                    .password("Test1234!")
                    .build();

            given(userRepository.findByEmail(request.getEmail())).willReturn(Optional.empty());

            // when & then
            assertThatThrownBy(() -> authService.loginAsync(request))
                    .isInstanceOf(UnauthorizedException.class);

            verify(jwtTokenProvider, never()).createAccessToken(anyLong(), anyString(), anyString());
        }

        @Test
        @DisplayName("로그인 실패 - 비활성화된 사용자")
        void login_fail_inactiveUser() {
            // given
            UserLoginRequest request = UserLoginRequest.builder()
                    .email("test@example.com")
                    .password("Test1234!")
                    .build();

            User user = User.builder()
                    .id(1L)
                    .email(request.getEmail())
                    .passwordHash("encodedPassword")
                    .isActive(false) // 비활성화 상태
                    .build();

            given(userRepository.findByEmail(request.getEmail())).willReturn(Optional.of(user));

            // when & then
            assertThatThrownBy(() -> authService.loginAsync(request))
                    .isInstanceOf(UnauthorizedException.class);
        }
    }

    @Nested
    @DisplayName("로그아웃 테스트")
    class LogoutTest {

        @Test
        @DisplayName("로그아웃 성공")
        void logout_success() {
            // given
            Long userId = 1L;
            User user = User.builder()
                    .id(userId)
                    .email("test@example.com")
                    .username("testuser")
                    .isOnline(true)
                    .build();

            given(userRepository.findById(userId)).willReturn(Optional.of(user));
            given(userRepository.save(any(User.class))).willReturn(user);

            // when
            authService.logout(userId);

            // then
            verify(userRepository).findById(userId);
            verify(userRepository).save(any(User.class));
            verify(onlineStatusService).setOffline(userId);
        }

        @Test
        @DisplayName("로그아웃 - 존재하지 않는 사용자 (무시)")
        void logout_userNotFound() {
            // given
            Long userId = 999L;
            given(userRepository.findById(userId)).willReturn(Optional.empty());

            // when
            authService.logout(userId);

            // then - 에러 없이 처리됨
            verify(userRepository).findById(userId);
            verify(userRepository, never()).save(any(User.class));
            verify(onlineStatusService, never()).setOffline(anyLong());
        }
    }
}
