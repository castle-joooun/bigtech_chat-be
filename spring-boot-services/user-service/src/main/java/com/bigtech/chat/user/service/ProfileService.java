package com.bigtech.chat.user.service;

import com.bigtech.chat.common.cache.CacheService;
import com.bigtech.chat.common.exception.ErrorCode;
import com.bigtech.chat.common.exception.ResourceNotFoundException;
import com.bigtech.chat.user.dto.ProfileUpdateRequest;
import com.bigtech.chat.user.entity.User;
import com.bigtech.chat.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * 프로필 서비스
 */
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
@Slf4j
public class ProfileService {

    private final UserRepository userRepository;
    private final CacheService cacheService;

    private static final String PROFILE_CACHE_PREFIX = "user:profile:";

    /**
     * 프로필 조회
     */
    public User getProfile(Long userId) {
        return userRepository.findByIdAndIsActiveTrue(userId)
                .orElseThrow(() -> new ResourceNotFoundException(ErrorCode.USER_NOT_FOUND));
    }

    /**
     * 프로필 수정
     */
    @Transactional
    public User updateProfile(Long userId, ProfileUpdateRequest request) {
        User user = userRepository.findById(userId)
                .orElseThrow(() -> new ResourceNotFoundException(ErrorCode.USER_NOT_FOUND));

        // 필드 업데이트
        if (request.getDisplayName() != null) {
            user.setDisplayName(request.getDisplayName());
        }

        if (request.getStatusMessage() != null) {
            user.setStatusMessage(request.getStatusMessage());
        }

        User savedUser = userRepository.save(user);

        // 캐시 무효화
        invalidateProfileCache(userId);

        log.info("Profile updated: userId={}", userId);

        return savedUser;
    }

    private void invalidateProfileCache(Long userId) {
        cacheService.delete(PROFILE_CACHE_PREFIX + userId);
    }
}
