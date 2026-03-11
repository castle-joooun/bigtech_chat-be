package com.bigtech.chat.user.controller;

import com.bigtech.chat.common.exception.ConflictException;
import com.bigtech.chat.common.exception.ErrorCode;
import com.bigtech.chat.common.exception.GlobalExceptionHandler;
import com.bigtech.chat.common.exception.UnauthorizedException;
import com.bigtech.chat.user.dto.TokenResponse;
import com.bigtech.chat.user.dto.UserCreateRequest;
import com.bigtech.chat.user.dto.UserLoginRequest;
import com.bigtech.chat.user.entity.User;
import com.bigtech.chat.user.service.AuthService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import java.util.concurrent.CompletableFuture;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultHandlers.print;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * AuthController API Test
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("AuthController API Test")
class AuthControllerTest {

    private MockMvc mockMvc;

    @Mock
    private AuthService authService;

    @InjectMocks
    private AuthController authController;

    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() {
        objectMapper = new ObjectMapper();
        mockMvc = MockMvcBuilders
                .standaloneSetup(authController)
                .setControllerAdvice(new GlobalExceptionHandler())
                .build();
    }

    @Nested
    @DisplayName("POST /api/auth/register")
    class RegisterTest {

        @Test
        @DisplayName("회원가입 성공 - 201 Created")
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
                    .displayName(request.getDisplayName())
                    .isActive(true)
                    .isOnline(false)
                    .build();

            given(authService.registerAsync(any(UserCreateRequest.class)))
                    .willReturn(CompletableFuture.completedFuture(savedUser));

            // when & then
            mockMvc.perform(post("/api/auth/register")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(request)))
                    .andDo(print())
                    .andExpect(status().isCreated())
                    .andExpect(jsonPath("$.id").value(1L))
                    .andExpect(jsonPath("$.email").value("test@example.com"))
                    .andExpect(jsonPath("$.username").value("testuser"));

            verify(authService).registerAsync(any(UserCreateRequest.class));
        }

        @Test
        @DisplayName("회원가입 실패 - 중복 이메일 (409 Conflict)")
        void register_fail_duplicateEmail() throws Exception {
            // given
            UserCreateRequest request = UserCreateRequest.builder()
                    .email("existing@example.com")
                    .username("newuser")
                    .password("Test1234!")
                    .build();

            given(authService.registerAsync(any(UserCreateRequest.class)))
                    .willThrow(new ConflictException(ErrorCode.EMAIL_ALREADY_EXISTS));

            // when & then
            mockMvc.perform(post("/api/auth/register")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(request)))
                    .andDo(print())
                    .andExpect(status().isConflict())
                    .andExpect(jsonPath("$.error").value("EMAIL_ALREADY_EXISTS"));
        }

        @Test
        @DisplayName("회원가입 실패 - 유효성 검증 오류 (400 Bad Request)")
        void register_fail_validation() throws Exception {
            // given - 이메일 형식 오류
            UserCreateRequest request = UserCreateRequest.builder()
                    .email("invalid-email")
                    .username("testuser")
                    .password("Test1234!")
                    .build();

            // when & then
            mockMvc.perform(post("/api/auth/register")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(request)))
                    .andDo(print())
                    .andExpect(status().isBadRequest());
        }
    }

    @Nested
    @DisplayName("POST /api/auth/login/json")
    class LoginTest {

        @Test
        @DisplayName("로그인 성공 - 200 OK")
        void login_success() throws Exception {
            // given
            UserLoginRequest request = UserLoginRequest.builder()
                    .email("test@example.com")
                    .password("Test1234!")
                    .build();

            TokenResponse tokenResponse = TokenResponse.builder()
                    .accessToken("jwt.token.here")
                    .expiresIn(86400)
                    .build();

            given(authService.loginAsync(any(UserLoginRequest.class)))
                    .willReturn(CompletableFuture.completedFuture(tokenResponse));

            // when & then
            mockMvc.perform(post("/api/auth/login/json")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(request)))
                    .andDo(print())
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.accessToken").value("jwt.token.here"))
                    .andExpect(jsonPath("$.expiresIn").value(86400));

            verify(authService).loginAsync(any(UserLoginRequest.class));
        }

        @Test
        @DisplayName("로그인 실패 - 잘못된 인증 정보 (401 Unauthorized)")
        void login_fail_invalidCredentials() throws Exception {
            // given
            UserLoginRequest request = UserLoginRequest.builder()
                    .email("test@example.com")
                    .password("WrongPassword!")
                    .build();

            given(authService.loginAsync(any(UserLoginRequest.class)))
                    .willThrow(new UnauthorizedException(ErrorCode.INVALID_CREDENTIALS));

            // when & then
            mockMvc.perform(post("/api/auth/login/json")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(request)))
                    .andDo(print())
                    .andExpect(status().isUnauthorized())
                    .andExpect(jsonPath("$.error").value("INVALID_CREDENTIALS"));
        }

        @Test
        @DisplayName("로그인 실패 - 유효성 검증 오류 (400 Bad Request)")
        void login_fail_validation() throws Exception {
            // given - 이메일 누락
            UserLoginRequest request = UserLoginRequest.builder()
                    .email("")
                    .password("Test1234!")
                    .build();

            // when & then
            mockMvc.perform(post("/api/auth/login/json")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(request)))
                    .andDo(print())
                    .andExpect(status().isBadRequest());
        }
    }

    @Nested
    @DisplayName("POST /api/auth/login (Form)")
    class LoginFormTest {

        @Test
        @DisplayName("Form 로그인 성공 - 200 OK")
        void loginForm_success() throws Exception {
            // given
            TokenResponse tokenResponse = TokenResponse.builder()
                    .accessToken("jwt.token.here")
                    .expiresIn(86400)
                    .build();

            given(authService.loginAsync(any(UserLoginRequest.class)))
                    .willReturn(CompletableFuture.completedFuture(tokenResponse));

            // when & then
            mockMvc.perform(post("/api/auth/login")
                            .contentType(MediaType.APPLICATION_FORM_URLENCODED)
                            .param("username", "test@example.com")
                            .param("password", "Test1234!"))
                    .andDo(print())
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.accessToken").value("jwt.token.here"));

            verify(authService).loginAsync(any(UserLoginRequest.class));
        }
    }
}
