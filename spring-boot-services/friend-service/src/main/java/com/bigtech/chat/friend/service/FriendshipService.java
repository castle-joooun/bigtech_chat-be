package com.bigtech.chat.friend.service;

import com.bigtech.chat.common.cache.CacheService;
import com.bigtech.chat.common.client.UserProfile;
import com.bigtech.chat.common.client.UserServiceClient;
import com.bigtech.chat.common.exception.BusinessLogicException;
import com.bigtech.chat.common.exception.ConflictException;
import com.bigtech.chat.common.exception.ErrorCode;
import com.bigtech.chat.common.exception.ResourceNotFoundException;
import com.bigtech.chat.common.kafka.KafkaProducerService;
import com.bigtech.chat.common.kafka.events.FriendRequestAcceptedEvent;
import com.bigtech.chat.common.kafka.events.FriendRequestSentEvent;
import com.bigtech.chat.friend.dto.FriendListResponse;
import com.bigtech.chat.friend.dto.FriendRequestListResponse;
import com.bigtech.chat.friend.entity.Friendship;
import com.bigtech.chat.friend.entity.FriendshipStatus;
import com.bigtech.chat.friend.repository.FriendshipRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.function.Function;
import java.util.stream.Collectors;

/**
 * 친구 관계 서비스
 *
 * MSA 원칙에 따라 User 정보는 user-service API를 통해 조회합니다.
 */
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
@Slf4j
public class FriendshipService {

    private final FriendshipRepository friendshipRepository;
    private final CacheService cacheService;
    private final KafkaProducerService kafkaProducerService;
    private final UserServiceClient userServiceClient;

    @Value("${kafka.topics.friend-events:friend.events}")
    private String friendEventsTopic;

    private static final String FRIEND_LIST_CACHE_PREFIX = "friend:list:";
    private static final String FRIEND_REQUESTS_CACHE_PREFIX = "friend:requests:";

    /**
     * 친구 요청 전송
     *
     * @param requesterUsername JWT 토큰에서 추출한 요청자 username (HTTP 호출 제거)
     */
    @Transactional
    public Friendship sendFriendRequest(Long requesterId, String requesterUsername, Long targetId) {
        // 자기 자신에게 요청 불가
        if (requesterId.equals(targetId)) {
            throw new BusinessLogicException(ErrorCode.CANNOT_FRIEND_SELF);
        }

        // 대상 사용자 존재 확인 + 프로필 조회 (1 HTTP call로 통합)
        // 기존: userExists() + 이벤트에서 2x getUserById() = 3 HTTP calls
        // 최적화: getUserById() 1회로 존재 확인 + 프로필 동시 획득
        UserProfile targetProfile = userServiceClient.getUserById(targetId)
                .orElseThrow(() -> new ResourceNotFoundException(ErrorCode.USER_NOT_FOUND));

        // 기존 관계 확인
        Optional<Friendship> existing = friendshipRepository.findByUserIds(requesterId, targetId);
        if (existing.isPresent()) {
            Friendship f = existing.get();
            if (f.isAccepted()) {
                throw new ConflictException(ErrorCode.FRIENDSHIP_ALREADY_EXISTS);
            } else {
                throw new ConflictException(ErrorCode.FRIEND_REQUEST_ALREADY_EXISTS);
            }
        }

        // 친구 요청 생성
        Friendship friendship = Friendship.builder()
                .userId1(requesterId)
                .userId2(targetId)
                .status(FriendshipStatus.PENDING)
                .build();

        Friendship saved = friendshipRepository.save(friendship);
        log.info("Friend request sent: {} -> {}", requesterId, targetId);

        // 캐시 무효화
        invalidateCache(requesterId, targetId);

        // Kafka 이벤트 발행 (이미 조회한 프로필 재사용 → 추가 HTTP 호출 0)
        publishFriendRequestSentEvent(saved, requesterUsername, targetProfile.getUsername());

        return saved;
    }

    /**
     * 친구 요청 수락
     *
     * @param accepterUsername JWT 토큰에서 추출한 수락자 username (HTTP 호출 제거)
     */
    @Transactional
    public Friendship acceptFriendRequest(Long requesterId, Long currentUserId, String accepterUsername) {
        Friendship friendship = friendshipRepository
                .findByRequesterAndAddresseeAndStatus(requesterId, currentUserId, FriendshipStatus.PENDING)
                .orElseThrow(() -> new ResourceNotFoundException(ErrorCode.FRIENDSHIP_NOT_FOUND));

        friendship.accept();
        Friendship saved = friendshipRepository.save(friendship);
        log.info("Friend request accepted: {} <- {}", currentUserId, requesterId);

        // 캐시 무효화
        invalidateCache(requesterId, currentUserId);

        // Kafka 이벤트 발행 (JWT username 사용 → HTTP 호출 최소화)
        publishFriendRequestAcceptedEvent(saved, accepterUsername);

        return saved;
    }

    /**
     * 친구 요청 거절
     */
    @Transactional
    public void rejectFriendRequest(Long requesterId, Long currentUserId) {
        Friendship friendship = friendshipRepository
                .findByRequesterAndAddresseeAndStatus(requesterId, currentUserId, FriendshipStatus.PENDING)
                .orElseThrow(() -> new ResourceNotFoundException(ErrorCode.FRIENDSHIP_NOT_FOUND));

        friendshipRepository.delete(friendship);
        log.info("Friend request rejected: {} <- {}", currentUserId, requesterId);

        // 캐시 무효화
        invalidateCache(requesterId, currentUserId);
    }

    /**
     * 친구 요청 취소
     */
    @Transactional
    public void cancelFriendRequest(Long currentUserId, Long targetId) {
        Friendship friendship = friendshipRepository
                .findByRequesterAndAddresseeAndStatus(currentUserId, targetId, FriendshipStatus.PENDING)
                .orElseThrow(() -> new ResourceNotFoundException(ErrorCode.FRIENDSHIP_NOT_FOUND));

        friendshipRepository.delete(friendship);
        log.info("Friend request cancelled: {} -> {}", currentUserId, targetId);

        // 캐시 무효화
        invalidateCache(currentUserId, targetId);
    }

    /**
     * 친구 목록 조회
     *
     * user-service API를 통해 사용자 정보를 조회합니다.
     */
    public List<FriendListResponse> getFriendsList(Long userId) {
        List<Friendship> friendships = friendshipRepository.findAcceptedFriendships(userId);

        if (friendships.isEmpty()) {
            return new ArrayList<>();
        }

        // 친구 ID 목록 추출
        List<Long> friendIds = friendships.stream()
                .map(f -> f.getOtherUserId(userId))
                .collect(Collectors.toList());

        // user-service API로 사용자 정보 일괄 조회
        List<UserProfile> users = userServiceClient.getUsersByIds(friendIds);
        Map<Long, UserProfile> userMap = users.stream()
                .collect(Collectors.toMap(UserProfile::getId, Function.identity()));

        // 응답 생성
        List<FriendListResponse> friends = new ArrayList<>();
        for (Friendship f : friendships) {
            Long friendId = f.getOtherUserId(userId);
            UserProfile user = userMap.get(friendId);

            if (user != null) {
                friends.add(FriendListResponse.builder()
                        .userId(user.getId())
                        .username(user.getUsername())
                        .displayName(user.getDisplayName())
                        .email(user.getEmail())
                        .isOnline(user.getIsOnline())
                        .lastSeenAt(user.getLastSeenAt())
                        .build());
            } else {
                // user-service에서 조회 실패 시 기본값
                friends.add(FriendListResponse.builder()
                        .userId(friendId)
                        .username("unknown")
                        .displayName("Unknown User")
                        .email(null)
                        .isOnline(false)
                        .lastSeenAt(null)
                        .build());
            }
        }

        return friends;
    }

    /**
     * 친구 요청 목록 조회
     *
     * user-service API를 통해 사용자 정보를 조회합니다.
     */
    public List<FriendRequestListResponse> getFriendRequests(Long userId) {
        List<FriendRequestListResponse> requests = new ArrayList<>();

        // 받은 요청
        List<Friendship> received = friendshipRepository.findReceivedRequests(userId);
        // 보낸 요청
        List<Friendship> sent = friendshipRepository.findSentRequests(userId);

        // 모든 관련 사용자 ID 수집
        List<Long> allUserIds = new ArrayList<>();
        received.forEach(f -> allUserIds.add(f.getUserId1()));
        sent.forEach(f -> allUserIds.add(f.getUserId2()));

        // user-service API로 사용자 정보 일괄 조회
        Map<Long, UserProfile> userMap = Map.of();
        if (!allUserIds.isEmpty()) {
            List<UserProfile> users = userServiceClient.getUsersByIds(allUserIds);
            userMap = users.stream()
                    .collect(Collectors.toMap(UserProfile::getId, Function.identity()));
        }

        // 받은 요청 처리
        for (Friendship f : received) {
            UserProfile user = userMap.get(f.getUserId1());
            requests.add(FriendRequestListResponse.builder()
                    .friendshipId(f.getId())
                    .userId(f.getUserId1())
                    .username(user != null ? user.getUsername() : "unknown")
                    .displayName(user != null ? user.getDisplayName() : "Unknown User")
                    .status("pending")
                    .createdAt(f.getCreatedAt())
                    .requestType("received")
                    .build());
        }

        // 보낸 요청 처리
        for (Friendship f : sent) {
            UserProfile user = userMap.get(f.getUserId2());
            requests.add(FriendRequestListResponse.builder()
                    .friendshipId(f.getId())
                    .userId(f.getUserId2())
                    .username(user != null ? user.getUsername() : "unknown")
                    .displayName(user != null ? user.getDisplayName() : "Unknown User")
                    .status("pending")
                    .createdAt(f.getCreatedAt())
                    .requestType("sent")
                    .build());
        }

        return requests;
    }

    /**
     * 친구 여부 확인
     */
    public boolean areFriends(Long userId1, Long userId2) {
        return friendshipRepository.areFriends(userId1, userId2);
    }

    /**
     * 친구 관계 조회
     */
    public Optional<Friendship> findFriendship(Long userId1, Long userId2) {
        return friendshipRepository.findByUserIds(userId1, userId2);
    }

    private void invalidateCache(Long userId1, Long userId2) {
        cacheService.delete(FRIEND_LIST_CACHE_PREFIX + userId1);
        cacheService.delete(FRIEND_LIST_CACHE_PREFIX + userId2);
        cacheService.delete(FRIEND_REQUESTS_CACHE_PREFIX + userId1);
        cacheService.delete(FRIEND_REQUESTS_CACHE_PREFIX + userId2);
    }

    private void publishFriendRequestSentEvent(Friendship friendship, String requesterUsername, String targetUsername) {
        try {
            // JWT username + 이미 조회한 target 프로필 사용 (추가 HTTP 호출 0)
            FriendRequestSentEvent event = new FriendRequestSentEvent(
                    friendship.getId(),
                    friendship.getUserId1(),
                    requesterUsername,
                    friendship.getUserId2(),
                    targetUsername
            );
            kafkaProducerService.publish(friendEventsTopic, event, String.valueOf(friendship.getId()));
        } catch (Exception e) {
            log.error("Failed to publish FriendRequestSentEvent: {}", e.getMessage());
        }
    }

    private void publishFriendRequestAcceptedEvent(Friendship friendship, String accepterUsername) {
        try {
            // 요청자 username만 user-service에서 조회 (수락자는 JWT에서 획득)
            // 기존 2 HTTP calls → 1 HTTP call (+ 인메모리 캐시 히트 가능성 높음)
            String requesterUsername = userServiceClient.getUserById(friendship.getUserId1())
                    .map(UserProfile::getUsername)
                    .orElse("unknown");

            // userId2 = 수락자 (currentUser)
            FriendRequestAcceptedEvent event = new FriendRequestAcceptedEvent(
                    friendship.getId(),
                    friendship.getUserId1(),
                    requesterUsername,
                    friendship.getUserId2(),
                    accepterUsername
            );
            kafkaProducerService.publish(friendEventsTopic, event, String.valueOf(friendship.getId()));
        } catch (Exception e) {
            log.error("Failed to publish FriendRequestAcceptedEvent: {}", e.getMessage());
        }
    }
}
