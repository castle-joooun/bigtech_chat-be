package com.bigtech.chat.user.controller;

import com.bigtech.chat.common.security.CurrentUser;
import com.bigtech.chat.common.security.JwtPayload;
import com.bigtech.chat.user.dto.TokenResponse;
import com.bigtech.chat.user.dto.UserCreateRequest;
import com.bigtech.chat.user.dto.UserLoginRequest;
import com.bigtech.chat.user.dto.UserResponse;
import com.bigtech.chat.user.service.AuthService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.Map;
import java.util.concurrent.CompletableFuture;

/**
 * 인증 컨트롤러
 *
 * register/login은 CompletableFuture를 반환하여
 * bcrypt 해싱 동안 Tomcat 요청 스레드를 즉시 해방.
 * Spring MVC의 비동기 요청 처리(Servlet 3.1+ async) 활용.
 */
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
@Tag(name = "Authentication", description = "인증 관련 API")
public class AuthController {

    private final AuthService authService;

    /**
     * 회원가입 (비동기)
     * CompletableFuture 반환 → Tomcat 스레드 즉시 해방 → bcrypt 완료 후 응답
     */
    @PostMapping("/register")
    @Operation(summary = "회원가입")
    public CompletableFuture<ResponseEntity<UserResponse>> register(
            @Valid @RequestBody UserCreateRequest request) {
        return authService.registerAsync(request)
                .thenApply(user -> ResponseEntity.status(HttpStatus.CREATED)
                        .body(UserResponse.from(user)));
    }

    /**
     * 로그인 - OAuth2 Form (비동기)
     */
    @PostMapping("/login")
    @Operation(summary = "로그인 (OAuth2 Form)")
    public CompletableFuture<ResponseEntity<TokenResponse>> login(
            @RequestParam String username,
            @RequestParam String password) {
        UserLoginRequest request = new UserLoginRequest(username, password);
        return authService.loginAsync(request)
                .thenApply(ResponseEntity::ok);
    }

    /**
     * 로그인 - JSON (비동기)
     */
    @PostMapping("/login/json")
    @Operation(summary = "로그인 (JSON)")
    public CompletableFuture<ResponseEntity<TokenResponse>> loginJson(
            @Valid @RequestBody UserLoginRequest request) {
        return authService.loginAsync(request)
                .thenApply(ResponseEntity::ok);
    }

    /**
     * 로그아웃 (동기 — bcrypt 미사용)
     */
    @PostMapping("/logout")
    @Operation(summary = "로그아웃")
    public ResponseEntity<Map<String, Object>> logout(
            @CurrentUser JwtPayload currentUser) {
        authService.logout(currentUser.getUserId());
        return ResponseEntity.ok(Map.of(
                "message", "Successfully logged out",
                "user_id", currentUser.getUserId()
        ));
    }
}
