package com.bigtech.chat.user.service;

import com.bigtech.chat.common.exception.ConflictException;
import com.bigtech.chat.common.exception.ErrorCode;
import com.bigtech.chat.common.exception.ResourceNotFoundException;
import com.bigtech.chat.common.exception.UnauthorizedException;
import com.bigtech.chat.common.kafka.KafkaProducerService;
import com.bigtech.chat.common.kafka.events.UserOnlineStatusChangedEvent;
import com.bigtech.chat.common.kafka.events.UserRegisteredEvent;
import com.bigtech.chat.common.security.JwtTokenProvider;
import com.bigtech.chat.user.dto.*;
import com.bigtech.chat.user.entity.User;
import com.bigtech.chat.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.support.TransactionTemplate;

import java.util.Optional;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.Executor;

/**
 * 인증 서비스
 *
 * BCrypt 해싱을 전용 스레드 풀(bcryptExecutor)에서 비동기 실행.
 * 컨트롤러가 CompletableFuture를 반환하여 Tomcat 요청 스레드 즉시 해방.
 * → 고부하 환경에서 스레드 풀 포화 방지
 */
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
@Slf4j
public class AuthService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final JwtTokenProvider jwtTokenProvider;
    private final OnlineStatusService onlineStatusService;
    private final KafkaProducerService kafkaProducerService;
    private final TransactionTemplate transactionTemplate;
    @Qualifier("bcryptExecutor")
    private final Executor bcryptExecutor;

    @Value("${kafka.topics.user-events:user.events}")
    private String userEventsTopic;

    @Value("${kafka.topics.user-online-status:user.online_status}")
    private String userOnlineStatusTopic;

    /**
     * 회원가입 (비동기)
     * bcrypt 해싱을 별도 스레드 풀에서 실행하고 CompletableFuture로 반환.
     * Tomcat 요청 스레드가 .get()으로 블로킹되지 않고 즉시 해방됨.
     */
    public CompletableFuture<User> registerAsync(UserCreateRequest request) {
        // 1. 중복 검사 (빠른 DB 조회 — 현재 스레드에서 실행)
        if (userRepository.existsByEmail(request.getEmail())) {
            throw new ConflictException(ErrorCode.EMAIL_ALREADY_EXISTS);
        }
        if (userRepository.existsByUsername(request.getUsername())) {
            throw new ConflictException(ErrorCode.USERNAME_ALREADY_EXISTS);
        }

        // 2. bcrypt 해싱 → 전용 스레드 풀에서 실행, 완료 후 DB 저장
        return CompletableFuture.supplyAsync(
                () -> passwordEncoder.encode(request.getPassword()),
                bcryptExecutor
        ).thenApply(passwordHash -> {
            // 3. 트랜잭션 내에서 사용자 저장
            User savedUser = transactionTemplate.execute(status -> {
                User user = User.builder()
                        .email(request.getEmail())
                        .username(request.getUsername())
                        .passwordHash(passwordHash)
                        .displayName(request.getDisplayName() != null
                                ? request.getDisplayName() : request.getUsername())
                        .build();
                return userRepository.save(user);
            });

            log.info("User registered: id={}, email={}", savedUser.getId(), savedUser.getEmail());
            publishUserRegisteredEvent(savedUser);
            return savedUser;
        });
    }

    /**
     * 로그인 (비동기)
     * bcrypt 검증을 별도 스레드 풀에서 실행하고 CompletableFuture로 반환.
     */
    public CompletableFuture<TokenResponse> loginAsync(UserLoginRequest request) {
        // 1. 사용자 조회 (빠른 DB 조회 — 현재 스레드에서 실행)
        User user = userRepository.findByEmail(request.getEmail())
                .filter(User::getIsActive)
                .orElseThrow(() -> new UnauthorizedException(ErrorCode.INVALID_CREDENTIALS));

        // 2. bcrypt 검증 → 전용 스레드 풀에서 실행
        return CompletableFuture.supplyAsync(
                () -> passwordEncoder.matches(request.getPassword(), user.getPasswordHash()),
                bcryptExecutor
        ).thenApply(matches -> {
            if (!matches) {
                throw new UnauthorizedException(ErrorCode.INVALID_CREDENTIALS);
            }

            // 3. 트랜잭션 내에서 후처리
            transactionTemplate.executeWithoutResult(status -> {
                user.goOnline();
                userRepository.save(user);
            });

            // JWT 토큰 생성
            String token = jwtTokenProvider.createAccessToken(
                    user.getId(),
                    user.getEmail(),
                    user.getUsername()
            );

            // Redis 온라인 상태
            onlineStatusService.setOnline(user.getId());

            // Kafka 이벤트
            publishOnlineStatusEvent(user.getId(), true);

            log.info("User logged in: id={}", user.getId());

            return TokenResponse.builder()
                    .accessToken(token)
                    .expiresIn(jwtTokenProvider.getExpirationSeconds())
                    .build();
        });
    }

    /**
     * 로그아웃 (동기 — bcrypt 미사용)
     */
    @Transactional
    public void logout(Long userId) {
        userRepository.findById(userId).ifPresent(user -> {
            user.goOffline();
            userRepository.save(user);
            onlineStatusService.setOffline(userId);
            publishOnlineStatusEvent(userId, false);
            log.info("User logged out: id={}", userId);
        });
    }

    /**
     * ID로 사용자 조회
     */
    public User findById(Long userId) {
        return userRepository.findByIdAndIsActiveTrue(userId)
                .orElseThrow(() -> new ResourceNotFoundException(ErrorCode.USER_NOT_FOUND));
    }

    /**
     * 이메일로 사용자 조회
     */
    public Optional<User> findByEmail(String email) {
        return userRepository.findByEmail(email);
    }

    private void publishUserRegisteredEvent(User user) {
        try {
            UserRegisteredEvent event = new UserRegisteredEvent(
                    user.getId(),
                    user.getEmail(),
                    user.getUsername(),
                    user.getDisplayName()
            );
            kafkaProducerService.publish(userEventsTopic, event, String.valueOf(user.getId()));
        } catch (Exception e) {
            log.error("Failed to publish UserRegisteredEvent: {}", e.getMessage());
        }
    }

    private void publishOnlineStatusEvent(Long userId, boolean isOnline) {
        try {
            UserOnlineStatusChangedEvent event = new UserOnlineStatusChangedEvent(userId, isOnline);
            kafkaProducerService.publish(userOnlineStatusTopic, event, String.valueOf(userId));
        } catch (Exception e) {
            log.error("Failed to publish UserOnlineStatusChangedEvent: {}", e.getMessage());
        }
    }
}
