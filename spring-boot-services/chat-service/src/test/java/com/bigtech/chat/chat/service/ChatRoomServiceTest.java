package com.bigtech.chat.chat.service;

import com.bigtech.chat.chat.dto.ChatRoomResponse;
import com.bigtech.chat.chat.entity.ChatRoom;
import com.bigtech.chat.chat.repository.ChatRoomRepository;
import com.bigtech.chat.chat.repository.MessageRepository;
import com.bigtech.chat.common.cache.CacheService;
import com.bigtech.chat.common.client.UserProfile;
import com.bigtech.chat.common.client.UserServiceClient;
import com.bigtech.chat.common.exception.BusinessLogicException;
import com.bigtech.chat.common.exception.ErrorCode;
import com.bigtech.chat.common.exception.ResourceNotFoundException;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import org.springframework.data.domain.Pageable;

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
 * ChatRoomService Unit Test
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("ChatRoomService Unit Test")
class ChatRoomServiceTest {

    @Mock
    private ChatRoomRepository chatRoomRepository;

    @Mock
    private MessageRepository messageRepository;

    @Mock
    private CacheService cacheService;

    @Mock
    private UserServiceClient userServiceClient;

    @InjectMocks
    private ChatRoomService chatRoomService;

    @Nested
    @DisplayName("채팅방 조회/생성 테스트")
    class GetOrCreateChatRoomTest {

        @Test
        @DisplayName("새 채팅방 생성")
        void getOrCreateChatRoom_create() {
            // given
            Long currentUserId = 1L;
            Long targetUserId = 2L;

            UserProfile targetUser = createUserProfile(targetUserId, "targetuser");

            ChatRoom savedRoom = ChatRoom.builder()
                    .id(1L)
                    .user1Id(currentUserId)
                    .user2Id(targetUserId)
                    .build();

            given(userServiceClient.getUserById(targetUserId)).willReturn(Optional.of(targetUser));
            given(chatRoomRepository.findByUsers(currentUserId, targetUserId)).willReturn(Optional.empty());
            given(chatRoomRepository.save(any(ChatRoom.class))).willReturn(savedRoom);

            // when
            ChatRoomResponse result = chatRoomService.getOrCreateChatRoom(currentUserId, targetUserId);

            // then
            assertThat(result).isNotNull();
            assertThat(result.getId()).isEqualTo(1L);

            verify(chatRoomRepository).save(any(ChatRoom.class));
            verify(cacheService, times(2)).delete(anyString()); // 양쪽 캐시 무효화
        }

        @Test
        @DisplayName("기존 채팅방 반환")
        void getOrCreateChatRoom_existing() {
            // given
            Long currentUserId = 1L;
            Long targetUserId = 2L;

            UserProfile targetUser = createUserProfile(targetUserId, "targetuser");

            ChatRoom existingRoom = ChatRoom.builder()
                    .id(1L)
                    .user1Id(currentUserId)
                    .user2Id(targetUserId)
                    .build();

            given(userServiceClient.getUserById(targetUserId)).willReturn(Optional.of(targetUser));
            given(chatRoomRepository.findByUsers(currentUserId, targetUserId)).willReturn(Optional.of(existingRoom));
            // 기존 채팅방의 타임스탬프 갱신 시 save 호출됨
            given(chatRoomRepository.save(any(ChatRoom.class))).willReturn(existingRoom);

            // when
            ChatRoomResponse result = chatRoomService.getOrCreateChatRoom(currentUserId, targetUserId);

            // then
            assertThat(result).isNotNull();
            assertThat(result.getId()).isEqualTo(1L);

            // 타임스탬프 갱신을 위해 save가 한 번 호출됨
            verify(chatRoomRepository, times(1)).save(any(ChatRoom.class));
        }

        @Test
        @DisplayName("자기 자신과 채팅 불가")
        void getOrCreateChatRoom_fail_self() {
            // given
            Long userId = 1L;

            // when & then
            assertThatThrownBy(() -> chatRoomService.getOrCreateChatRoom(userId, userId))
                    .isInstanceOf(BusinessLogicException.class)
                    .satisfies(ex -> {
                        BusinessLogicException be = (BusinessLogicException) ex;
                        assertThat(be.getErrorCode()).isEqualTo(ErrorCode.CANNOT_CHAT_SELF);
                    });

            verify(chatRoomRepository, never()).save(any(ChatRoom.class));
        }

        @Test
        @DisplayName("존재하지 않는 사용자와 채팅 불가")
        void getOrCreateChatRoom_fail_userNotFound() {
            // given
            Long currentUserId = 1L;
            Long targetUserId = 999L;

            given(userServiceClient.getUserById(targetUserId)).willReturn(Optional.empty());

            // when & then
            assertThatThrownBy(() -> chatRoomService.getOrCreateChatRoom(currentUserId, targetUserId))
                    .isInstanceOf(ResourceNotFoundException.class)
                    .satisfies(ex -> {
                        ResourceNotFoundException rnfe = (ResourceNotFoundException) ex;
                        assertThat(rnfe.getErrorCode()).isEqualTo(ErrorCode.USER_NOT_FOUND);
                    });
        }
    }

    @Nested
    @DisplayName("채팅방 목록 조회 테스트")
    class GetChatRoomsTest {

        @Test
        @DisplayName("채팅방 목록 조회 성공")
        void getChatRooms_success() {
            // given
            Long userId = 1L;
            int skip = 0;
            int limit = 50;

            ChatRoom room1 = ChatRoom.builder()
                    .id(1L)
                    .user1Id(userId)
                    .user2Id(2L)
                    .build();

            ChatRoom room2 = ChatRoom.builder()
                    .id(2L)
                    .user1Id(3L)
                    .user2Id(userId)
                    .build();

            // 캐시 MISS 시뮬레이션
            given(cacheService.get(anyString(), eq(List.class))).willReturn(Optional.empty());
            given(chatRoomRepository.findByUserId(eq(userId), any(Pageable.class)))
                    .willReturn(Arrays.asList(room1, room2));

            List<UserProfile> userProfiles = Arrays.asList(
                    createUserProfile(2L, "user2"),
                    createUserProfile(3L, "user3")
            );
            given(userServiceClient.getUsersByIds(anyList())).willReturn(userProfiles);
            given(messageRepository.findFirstActiveByRoomId(anyLong())).willReturn(null);

            // when
            List<ChatRoomResponse> result = chatRoomService.getChatRooms(userId, skip, limit);

            // then
            assertThat(result).hasSize(2);
        }

        @Test
        @DisplayName("채팅방 목록 조회 - 채팅방 없음")
        void getChatRooms_empty() {
            // given
            Long userId = 1L;
            int skip = 0;
            int limit = 50;

            // 캐시 MISS 시뮬레이션
            given(cacheService.get(anyString(), eq(List.class))).willReturn(Optional.empty());
            given(chatRoomRepository.findByUserId(eq(userId), any(Pageable.class)))
                    .willReturn(Collections.emptyList());

            // when
            List<ChatRoomResponse> result = chatRoomService.getChatRooms(userId, skip, limit);

            // then
            assertThat(result).isEmpty();
        }
    }

    @Nested
    @DisplayName("채팅방 조회 테스트")
    class GetChatRoomTest {

        @Test
        @DisplayName("채팅방 조회 성공")
        void getChatRoom_success() {
            // given
            Long roomId = 1L;

            ChatRoom room = ChatRoom.builder()
                    .id(roomId)
                    .user1Id(1L)
                    .user2Id(2L)
                    .build();

            given(chatRoomRepository.findById(roomId)).willReturn(Optional.of(room));

            // when
            ChatRoom result = chatRoomService.getChatRoom(roomId);

            // then
            assertThat(result).isNotNull();
            assertThat(result.getId()).isEqualTo(roomId);
        }

        @Test
        @DisplayName("채팅방 조회 실패 - 존재하지 않음")
        void getChatRoom_fail_notFound() {
            // given
            Long roomId = 999L;
            given(chatRoomRepository.findById(roomId)).willReturn(Optional.empty());

            // when & then
            assertThatThrownBy(() -> chatRoomService.getChatRoom(roomId))
                    .isInstanceOf(ResourceNotFoundException.class)
                    .satisfies(ex -> {
                        ResourceNotFoundException rnfe = (ResourceNotFoundException) ex;
                        assertThat(rnfe.getErrorCode()).isEqualTo(ErrorCode.CHATROOM_NOT_FOUND);
                    });
        }
    }

    @Nested
    @DisplayName("채팅방 접근 권한 테스트")
    class ValidateAccessTest {

        @Test
        @DisplayName("접근 권한 검증 성공")
        void validateAccess_success() {
            // given
            Long roomId = 1L;
            Long userId = 1L;

            ChatRoom room = ChatRoom.builder()
                    .id(roomId)
                    .user1Id(userId)
                    .user2Id(2L)
                    .build();

            given(chatRoomRepository.findById(roomId)).willReturn(Optional.of(room));

            // when & then - 예외 발생하지 않음
            chatRoomService.validateAccess(roomId, userId);
        }

        @Test
        @DisplayName("접근 권한 검증 실패 - 권한 없음")
        void validateAccess_fail_denied() {
            // given
            Long roomId = 1L;
            Long userId = 3L; // 채팅방에 참여하지 않은 사용자

            ChatRoom room = ChatRoom.builder()
                    .id(roomId)
                    .user1Id(1L)
                    .user2Id(2L)
                    .build();

            given(chatRoomRepository.findById(roomId)).willReturn(Optional.of(room));

            // when & then
            assertThatThrownBy(() -> chatRoomService.validateAccess(roomId, userId))
                    .isInstanceOf(BusinessLogicException.class)
                    .satisfies(ex -> {
                        BusinessLogicException be = (BusinessLogicException) ex;
                        assertThat(be.getErrorCode()).isEqualTo(ErrorCode.CHATROOM_ACCESS_DENIED);
                    });
        }
    }

    @Nested
    @DisplayName("채팅방 존재 확인 테스트")
    class ExistsBetweenUsersTest {

        @Test
        @DisplayName("채팅방 존재 - true")
        void existsBetweenUsers_true() {
            // given
            Long userId1 = 1L;
            Long userId2 = 2L;

            given(chatRoomRepository.existsByUsers(userId1, userId2)).willReturn(true);

            // when
            boolean result = chatRoomService.existsBetweenUsers(userId1, userId2);

            // then
            assertThat(result).isTrue();
        }

        @Test
        @DisplayName("채팅방 존재 - false")
        void existsBetweenUsers_false() {
            // given
            Long userId1 = 1L;
            Long userId2 = 2L;

            given(chatRoomRepository.existsByUsers(userId1, userId2)).willReturn(false);

            // when
            boolean result = chatRoomService.existsBetweenUsers(userId1, userId2);

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
