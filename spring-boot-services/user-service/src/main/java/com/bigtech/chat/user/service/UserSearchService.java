package com.bigtech.chat.user.service;

import com.bigtech.chat.common.cache.CacheService;
import com.bigtech.chat.common.exception.ErrorCode;
import com.bigtech.chat.common.exception.ResourceNotFoundException;
import com.bigtech.chat.user.dto.UserSearchResponse;
import com.bigtech.chat.user.entity.User;
import com.bigtech.chat.user.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;

/**
 * 사용자 검색 서비스
 */
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
@Slf4j
public class UserSearchService {

    private final UserRepository userRepository;
    private final CacheService cacheService;

    private static final String SEARCH_CACHE_PREFIX = "user:search:";
    private static final int DEFAULT_LIMIT = 20;
    private static final int MAX_LIMIT = 100;

    /**
     * 사용자 검색
     */
    public List<UserSearchResponse> searchUsers(String query, Long currentUserId, int limit) {
        if (query == null || query.trim().isEmpty()) {
            return List.of();
        }

        // 제한 조정
        limit = Math.min(Math.max(limit, 1), MAX_LIMIT);

        List<User> users = userRepository.searchByUsernameOrDisplayName(
                query.trim(),
                currentUserId,
                PageRequest.of(0, limit)
        );

        return users.stream()
                .map(UserSearchResponse::from)
                .collect(Collectors.toList());
    }

    /**
     * ID로 사용자 조회
     */
    public User findById(Long userId) {
        return userRepository.findByIdAndIsActiveTrue(userId)
                .orElseThrow(() -> new ResourceNotFoundException(ErrorCode.USER_NOT_FOUND));
    }

    /**
     * 여러 ID로 사용자 조회
     */
    public List<User> findAllByIds(List<Long> userIds) {
        return userRepository.findAllById(userIds);
    }

    /**
     * 사용자 존재 여부 확인
     */
    public boolean existsById(Long userId) {
        return userRepository.existsById(userId);
    }
}
