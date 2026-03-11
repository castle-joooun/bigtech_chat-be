package com.bigtech.chat.friend.service;

import com.bigtech.chat.common.cache.CacheService;
import com.bigtech.chat.common.client.UserProfile;
import com.bigtech.chat.common.client.UserServiceClient;
import com.bigtech.chat.common.exception.BusinessLogicException;
import com.bigtech.chat.common.exception.ConflictException;
import com.bigtech.chat.common.exception.ErrorCode;
import com.bigtech.chat.common.exception.ResourceNotFoundException;
import com.bigtech.chat.common.kafka.KafkaProducerService;
import com.bigtech.chat.friend.dto.FriendListResponse;
import com.bigtech.chat.friend.entity.Friendship;
import com.bigtech.chat.friend.entity.FriendshipStatus;
import com.bigtech.chat.friend.repository.FriendshipRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.test.util.ReflectionTestUtils;

import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.Collections;
import java.util.List;
import java.util.Optional;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.*;

/**
 * FriendshipService Unit Test
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("FriendshipService Unit Test")
class FriendshipServiceTest {

    @Mock
    private FriendshipRepository friendshipRepository;

    @Mock
    private CacheService cacheService;

    @Mock
    private KafkaProducerService kafkaProducerService;

    @Mock
    private UserServiceClient userServiceClient;

    @InjectMocks
    private FriendshipService friendshipService;

    @BeforeEach
    void setUp() {
        ReflectionTestUtils.setField(friendshipService, "friendEventsTopic", "friend.events");
    }

    @Nested
    @DisplayName("친구 요청 전송 테스트")
    class SendFriendRequestTest {

        @Test
        @DisplayName("친구 요청 전송 성공")
        void sendFriendRequest_success() {
            // given
            Long requesterId = 1L;
            Long targetId = 2L;

            Friendship savedFriendship = Friendship.builder()
                    .id(1L)
                    .userId1(requesterId)
                    .userId2(targetId)
                    .status(FriendshipStatus.PENDING)
                    .build();

            given(userServiceClient.getUserById(targetId)).willReturn(Optional.of(createUserProfile(targetId, "user2")));
            given(friendshipRepository.findByUserIds(requesterId, targetId)).willReturn(Optional.empty());
            given(friendshipRepository.save(any(Friendship.class))).willReturn(savedFriendship);

            // when
            Friendship result = friendshipService.sendFriendRequest(requesterId, "requester", targetId);

            // then
            assertThat(result).isNotNull();
            assertThat(result.getUserId1()).isEqualTo(requesterId);
            assertThat(result.getUserId2()).isEqualTo(targetId);
            assertThat(result.getStatus()).isEqualTo(FriendshipStatus.PENDING);

            verify(friendshipRepository).save(any(Friendship.class));
            verify(cacheService, times(4)).delete(anyString()); // 양쪽 사용자의 캐시 무효화
        }

        @Test
        @DisplayName("친구 요청 실패 - 자기 자신")
        void sendFriendRequest_fail_self() {
            // given
            Long userId = 1L;

            // when & then
            assertThatThrownBy(() -> friendshipService.sendFriendRequest(userId, "testuser", userId))
                    .isInstanceOf(BusinessLogicException.class)
                    .satisfies(ex -> {
                        BusinessLogicException be = (BusinessLogicException) ex;
                        assertThat(be.getErrorCode()).isEqualTo(ErrorCode.CANNOT_FRIEND_SELF);
                    });

            verify(friendshipRepository, never()).save(any(Friendship.class));
        }

        @Test
        @DisplayName("친구 요청 실패 - 존재하지 않는 대상 사용자")
        void sendFriendRequest_fail_targetNotFound() {
            // given
            Long requesterId = 1L;
            Long targetId = 999L;

            given(userServiceClient.getUserById(targetId)).willReturn(Optional.empty());

            // when & then
            assertThatThrownBy(() -> friendshipService.sendFriendRequest(requesterId, "requester", targetId))
                    .isInstanceOf(ResourceNotFoundException.class)
                    .satisfies(ex -> {
                        ResourceNotFoundException rnfe = (ResourceNotFoundException) ex;
                        assertThat(rnfe.getErrorCode()).isEqualTo(ErrorCode.USER_NOT_FOUND);
                    });
        }

        @Test
        @DisplayName("친구 요청 실패 - 이미 친구 관계")
        void sendFriendRequest_fail_alreadyFriends() {
            // given
            Long requesterId = 1L;
            Long targetId = 2L;

            Friendship existingFriendship = Friendship.builder()
                    .id(1L)
                    .userId1(requesterId)
                    .userId2(targetId)
                    .status(FriendshipStatus.ACCEPTED)
                    .build();

            given(userServiceClient.getUserById(targetId)).willReturn(Optional.of(createUserProfile(targetId, "user2")));
            given(friendshipRepository.findByUserIds(requesterId, targetId)).willReturn(Optional.of(existingFriendship));

            // when & then
            assertThatThrownBy(() -> friendshipService.sendFriendRequest(requesterId, "requester", targetId))
                    .isInstanceOf(ConflictException.class)
                    .satisfies(ex -> {
                        ConflictException ce = (ConflictException) ex;
                        assertThat(ce.getErrorCode()).isEqualTo(ErrorCode.FRIENDSHIP_ALREADY_EXISTS);
                    });
        }

        @Test
        @DisplayName("친구 요청 실패 - 이미 요청 진행중")
        void sendFriendRequest_fail_alreadyPending() {
            // given
            Long requesterId = 1L;
            Long targetId = 2L;

            Friendship existingRequest = Friendship.builder()
                    .id(1L)
                    .userId1(requesterId)
                    .userId2(targetId)
                    .status(FriendshipStatus.PENDING)
                    .build();

            given(userServiceClient.getUserById(targetId)).willReturn(Optional.of(createUserProfile(targetId, "user2")));
            given(friendshipRepository.findByUserIds(requesterId, targetId)).willReturn(Optional.of(existingRequest));

            // when & then
            assertThatThrownBy(() -> friendshipService.sendFriendRequest(requesterId, "requester", targetId))
                    .isInstanceOf(ConflictException.class)
                    .satisfies(ex -> {
                        ConflictException ce = (ConflictException) ex;
                        assertThat(ce.getErrorCode()).isEqualTo(ErrorCode.FRIEND_REQUEST_ALREADY_EXISTS);
                    });
        }
    }

    @Nested
    @DisplayName("친구 요청 수락 테스트")
    class AcceptFriendRequestTest {

        @Test
        @DisplayName("친구 요청 수락 성공")
        void acceptFriendRequest_success() {
            // given
            Long requesterId = 1L;
            Long currentUserId = 2L;

            Friendship pendingFriendship = Friendship.builder()
                    .id(1L)
                    .userId1(requesterId)
                    .userId2(currentUserId)
                    .status(FriendshipStatus.PENDING)
                    .build();

            given(friendshipRepository.findByRequesterAndAddresseeAndStatus(
                    requesterId, currentUserId, FriendshipStatus.PENDING))
                    .willReturn(Optional.of(pendingFriendship));
            given(friendshipRepository.save(any(Friendship.class))).willReturn(pendingFriendship);
            given(userServiceClient.getUserById(requesterId)).willReturn(Optional.of(createUserProfile(requesterId, "user1")));

            // when
            Friendship result = friendshipService.acceptFriendRequest(requesterId, currentUserId, "accepter");

            // then
            assertThat(result).isNotNull();
            assertThat(result.getStatus()).isEqualTo(FriendshipStatus.ACCEPTED);

            verify(friendshipRepository).save(any(Friendship.class));
        }

        @Test
        @DisplayName("친구 요청 수락 실패 - 요청 없음")
        void acceptFriendRequest_fail_notFound() {
            // given
            Long requesterId = 1L;
            Long currentUserId = 2L;

            given(friendshipRepository.findByRequesterAndAddresseeAndStatus(
                    requesterId, currentUserId, FriendshipStatus.PENDING))
                    .willReturn(Optional.empty());

            // when & then
            assertThatThrownBy(() -> friendshipService.acceptFriendRequest(requesterId, currentUserId, "accepter"))
                    .isInstanceOf(ResourceNotFoundException.class)
                    .satisfies(ex -> {
                        ResourceNotFoundException rnfe = (ResourceNotFoundException) ex;
                        assertThat(rnfe.getErrorCode()).isEqualTo(ErrorCode.FRIENDSHIP_NOT_FOUND);
                    });
        }
    }

    @Nested
    @DisplayName("친구 목록 조회 테스트")
    class GetFriendsListTest {

        @Test
        @DisplayName("친구 목록 조회 성공")
        void getFriendsList_success() {
            // given
            Long userId = 1L;

            Friendship friendship1 = Friendship.builder()
                    .id(1L)
                    .userId1(userId)
                    .userId2(2L)
                    .status(FriendshipStatus.ACCEPTED)
                    .build();

            Friendship friendship2 = Friendship.builder()
                    .id(2L)
                    .userId1(3L)
                    .userId2(userId)
                    .status(FriendshipStatus.ACCEPTED)
                    .build();

            given(friendshipRepository.findAcceptedFriendships(userId))
                    .willReturn(Arrays.asList(friendship1, friendship2));

            List<UserProfile> userProfiles = Arrays.asList(
                    createUserProfile(2L, "user2"),
                    createUserProfile(3L, "user3")
            );
            given(userServiceClient.getUsersByIds(anyList())).willReturn(userProfiles);

            // when
            List<FriendListResponse> result = friendshipService.getFriendsList(userId);

            // then
            assertThat(result).hasSize(2);
            assertThat(result).extracting(FriendListResponse::getUserId)
                    .containsExactlyInAnyOrder(2L, 3L);
        }

        @Test
        @DisplayName("친구 목록 조회 - 친구 없음")
        void getFriendsList_empty() {
            // given
            Long userId = 1L;
            given(friendshipRepository.findAcceptedFriendships(userId))
                    .willReturn(Collections.emptyList());

            // when
            List<FriendListResponse> result = friendshipService.getFriendsList(userId);

            // then
            assertThat(result).isEmpty();
        }
    }

    @Nested
    @DisplayName("친구 여부 확인 테스트")
    class AreFriendsTest {

        @Test
        @DisplayName("친구 여부 확인 - 친구인 경우")
        void areFriends_true() {
            // given
            Long userId1 = 1L;
            Long userId2 = 2L;

            given(friendshipRepository.areFriends(userId1, userId2)).willReturn(true);

            // when
            boolean result = friendshipService.areFriends(userId1, userId2);

            // then
            assertThat(result).isTrue();
        }

        @Test
        @DisplayName("친구 여부 확인 - 친구가 아닌 경우")
        void areFriends_false() {
            // given
            Long userId1 = 1L;
            Long userId2 = 2L;

            given(friendshipRepository.areFriends(userId1, userId2)).willReturn(false);

            // when
            boolean result = friendshipService.areFriends(userId1, userId2);

            // then
            assertThat(result).isFalse();
        }
    }

    private UserProfile createUserProfile(Long id, String username) {
        return UserProfile.builder()
                .id(id)
                .username(username)
                .displayName("Display " + username)
                .email(username + "@example.com")
                .isOnline(false)
                .lastSeenAt(LocalDateTime.now())
                .build();
    }
}
