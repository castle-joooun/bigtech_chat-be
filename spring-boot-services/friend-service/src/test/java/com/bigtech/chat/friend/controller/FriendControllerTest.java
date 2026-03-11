package com.bigtech.chat.friend.controller;

import com.bigtech.chat.common.exception.BusinessLogicException;
import com.bigtech.chat.common.exception.ConflictException;
import com.bigtech.chat.common.exception.ErrorCode;
import com.bigtech.chat.common.exception.GlobalExceptionHandler;
import com.bigtech.chat.common.security.CurrentUserArgumentResolver;
import com.bigtech.chat.common.security.JwtPayload;
import com.bigtech.chat.friend.dto.FriendListResponse;
import com.bigtech.chat.friend.dto.FriendRequestListResponse;
import com.bigtech.chat.friend.dto.FriendshipCreateRequest;
import com.bigtech.chat.friend.dto.FriendshipStatusUpdateRequest;
import com.bigtech.chat.friend.entity.Friendship;
import com.bigtech.chat.friend.entity.FriendshipStatus;
import com.bigtech.chat.friend.service.FriendshipService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.core.MethodParameter;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.web.bind.support.WebDataBinderFactory;
import org.springframework.web.context.request.NativeWebRequest;
import org.springframework.web.method.support.HandlerMethodArgumentResolver;
import org.springframework.web.method.support.ModelAndViewContainer;

import java.time.LocalDateTime;
import java.util.Arrays;
import java.util.Collections;
import java.util.Date;
import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.doNothing;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
import static org.springframework.test.web.servlet.result.MockMvcResultHandlers.print;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * FriendController API Test
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("FriendController API Test")
class FriendControllerTest {

    private MockMvc mockMvc;

    @Mock
    private FriendshipService friendshipService;

    @InjectMocks
    private FriendController friendController;

    private ObjectMapper objectMapper;

    private static final Long CURRENT_USER_ID = 1L;
    private static final String CURRENT_USER_EMAIL = "test@example.com";
    private static final String CURRENT_USER_USERNAME = "testuser";

    @BeforeEach
    void setUp() {
        objectMapper = new ObjectMapper();

        // @CurrentUser 어노테이션 처리를 위한 ArgumentResolver
        HandlerMethodArgumentResolver currentUserResolver = new HandlerMethodArgumentResolver() {
            @Override
            public boolean supportsParameter(MethodParameter parameter) {
                return parameter.getParameterType().equals(JwtPayload.class);
            }

            @Override
            public Object resolveArgument(MethodParameter parameter, ModelAndViewContainer mavContainer,
                                          NativeWebRequest webRequest, WebDataBinderFactory binderFactory) {
                return JwtPayload.builder()
                        .userId(CURRENT_USER_ID)
                        .email(CURRENT_USER_EMAIL)
                        .username(CURRENT_USER_USERNAME)
                        .expiration(new Date(System.currentTimeMillis() + 86400000))
                        .build();
            }
        };

        mockMvc = MockMvcBuilders
                .standaloneSetup(friendController)
                .setControllerAdvice(new GlobalExceptionHandler())
                .setCustomArgumentResolvers(currentUserResolver)
                .build();
    }

    @Nested
    @DisplayName("POST /api/friends/request")
    class SendFriendRequestTest {

        @Test
        @DisplayName("친구 요청 전송 성공 - 201 Created")
        void sendFriendRequest_success() throws Exception {
            // given
            Long targetId = 2L;
            FriendshipCreateRequest request = new FriendshipCreateRequest();
            request.setUserId2(targetId);

            Friendship savedFriendship = Friendship.builder()
                    .id(1L)
                    .userId1(CURRENT_USER_ID)
                    .userId2(targetId)
                    .status(FriendshipStatus.PENDING)
                    .build();

            given(friendshipService.sendFriendRequest(CURRENT_USER_ID, CURRENT_USER_USERNAME, targetId))
                    .willReturn(savedFriendship);

            // when & then
            mockMvc.perform(post("/api/friends/request")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(request)))
                    .andDo(print())
                    .andExpect(status().isCreated())
                    .andExpect(jsonPath("$.id").value(1L))
                    .andExpect(jsonPath("$.status").value("pending"));

            verify(friendshipService).sendFriendRequest(CURRENT_USER_ID, CURRENT_USER_USERNAME, targetId);
        }

        @Test
        @DisplayName("친구 요청 실패 - 자기 자신 (400 Bad Request)")
        void sendFriendRequest_fail_self() throws Exception {
            // given
            FriendshipCreateRequest request = new FriendshipCreateRequest();
            request.setUserId2(CURRENT_USER_ID);

            given(friendshipService.sendFriendRequest(CURRENT_USER_ID, CURRENT_USER_USERNAME, CURRENT_USER_ID))
                    .willThrow(new BusinessLogicException(ErrorCode.CANNOT_FRIEND_SELF));

            // when & then
            mockMvc.perform(post("/api/friends/request")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(request)))
                    .andDo(print())
                    .andExpect(status().isUnprocessableEntity())
                    .andExpect(jsonPath("$.error").value("CANNOT_FRIEND_SELF"));
        }

        @Test
        @DisplayName("친구 요청 실패 - 이미 친구 관계 (409 Conflict)")
        void sendFriendRequest_fail_alreadyFriends() throws Exception {
            // given
            Long targetId = 2L;
            FriendshipCreateRequest request = new FriendshipCreateRequest();
            request.setUserId2(targetId);

            given(friendshipService.sendFriendRequest(CURRENT_USER_ID, CURRENT_USER_USERNAME, targetId))
                    .willThrow(new ConflictException(ErrorCode.FRIENDSHIP_ALREADY_EXISTS));

            // when & then
            mockMvc.perform(post("/api/friends/request")
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(request)))
                    .andDo(print())
                    .andExpect(status().isConflict())
                    .andExpect(jsonPath("$.error").value("FRIENDSHIP_ALREADY_EXISTS"));
        }
    }

    @Nested
    @DisplayName("GET /api/friends/list")
    class GetFriendsListTest {

        @Test
        @DisplayName("친구 목록 조회 성공 - 200 OK")
        void getFriendsList_success() throws Exception {
            // given
            List<FriendListResponse> friends = Arrays.asList(
                    FriendListResponse.builder()
                            .userId(2L)
                            .username("friend1")
                            .displayName("Friend One")
                            .email("friend1@example.com")
                            .isOnline(true)
                            .lastSeenAt(LocalDateTime.now())
                            .build(),
                    FriendListResponse.builder()
                            .userId(3L)
                            .username("friend2")
                            .displayName("Friend Two")
                            .email("friend2@example.com")
                            .isOnline(false)
                            .lastSeenAt(LocalDateTime.now().minusHours(1))
                            .build()
            );

            given(friendshipService.getFriendsList(CURRENT_USER_ID)).willReturn(friends);

            // when & then
            mockMvc.perform(get("/api/friends/list"))
                    .andDo(print())
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.length()").value(2))
                    .andExpect(jsonPath("$[0].userId").value(2L))
                    .andExpect(jsonPath("$[0].username").value("friend1"))
                    .andExpect(jsonPath("$[1].userId").value(3L));

            verify(friendshipService).getFriendsList(CURRENT_USER_ID);
        }

        @Test
        @DisplayName("친구 목록 조회 - 친구 없음 - 200 OK")
        void getFriendsList_empty() throws Exception {
            // given
            given(friendshipService.getFriendsList(CURRENT_USER_ID)).willReturn(Collections.emptyList());

            // when & then
            mockMvc.perform(get("/api/friends/list"))
                    .andDo(print())
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.length()").value(0));
        }
    }

    @Nested
    @DisplayName("GET /api/friends/requests")
    class GetFriendRequestsTest {

        @Test
        @DisplayName("친구 요청 목록 조회 성공 - 200 OK")
        void getFriendRequests_success() throws Exception {
            // given
            List<FriendRequestListResponse> requests = Arrays.asList(
                    FriendRequestListResponse.builder()
                            .friendshipId(1L)
                            .userId(2L)
                            .username("requester1")
                            .displayName("Requester One")
                            .status("pending")
                            .requestType("received")
                            .createdAt(LocalDateTime.now())
                            .build()
            );

            given(friendshipService.getFriendRequests(CURRENT_USER_ID)).willReturn(requests);

            // when & then
            mockMvc.perform(get("/api/friends/requests"))
                    .andDo(print())
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.length()").value(1))
                    .andExpect(jsonPath("$[0].requestType").value("received"));
        }
    }

    @Nested
    @DisplayName("PUT /api/friends/status/{requesterUserId}")
    class UpdateFriendRequestStatusTest {

        @Test
        @DisplayName("친구 요청 수락 성공 - 200 OK")
        void acceptFriendRequest_success() throws Exception {
            // given
            Long requesterUserId = 2L;
            FriendshipStatusUpdateRequest request = new FriendshipStatusUpdateRequest();
            request.setAction("accept");

            Friendship acceptedFriendship = Friendship.builder()
                    .id(1L)
                    .userId1(requesterUserId)
                    .userId2(CURRENT_USER_ID)
                    .status(FriendshipStatus.ACCEPTED)
                    .build();

            given(friendshipService.acceptFriendRequest(requesterUserId, CURRENT_USER_ID, CURRENT_USER_USERNAME))
                    .willReturn(acceptedFriendship);

            // when & then
            mockMvc.perform(put("/api/friends/status/{requesterUserId}", requesterUserId)
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(request)))
                    .andDo(print())
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.status").value("accepted"));
        }

        @Test
        @DisplayName("친구 요청 거절 성공 - 200 OK")
        void rejectFriendRequest_success() throws Exception {
            // given
            Long requesterUserId = 2L;
            FriendshipStatusUpdateRequest request = new FriendshipStatusUpdateRequest();
            request.setAction("reject");

            doNothing().when(friendshipService).rejectFriendRequest(requesterUserId, CURRENT_USER_ID);

            // when & then
            mockMvc.perform(put("/api/friends/status/{requesterUserId}", requesterUserId)
                            .contentType(MediaType.APPLICATION_JSON)
                            .content(objectMapper.writeValueAsString(request)))
                    .andDo(print())
                    .andExpect(status().isOk());

            verify(friendshipService).rejectFriendRequest(requesterUserId, CURRENT_USER_ID);
        }
    }

    @Nested
    @DisplayName("DELETE /api/friends/request/{targetUserId}")
    class CancelFriendRequestTest {

        @Test
        @DisplayName("친구 요청 취소 성공 - 200 OK")
        void cancelFriendRequest_success() throws Exception {
            // given
            Long targetUserId = 2L;

            doNothing().when(friendshipService).cancelFriendRequest(CURRENT_USER_ID, targetUserId);

            // when & then
            mockMvc.perform(delete("/api/friends/request/{targetUserId}", targetUserId))
                    .andDo(print())
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.message").value("Friend request cancelled"));

            verify(friendshipService).cancelFriendRequest(CURRENT_USER_ID, targetUserId);
        }
    }

    @Nested
    @DisplayName("GET /api/friends/check/{userId}")
    class CheckFriendshipTest {

        @Test
        @DisplayName("친구 여부 확인 - 친구인 경우")
        void checkFriendship_true() throws Exception {
            // given
            Long userId = 2L;
            given(friendshipService.areFriends(CURRENT_USER_ID, userId)).willReturn(true);

            // when & then
            mockMvc.perform(get("/api/friends/check/{userId}", userId))
                    .andDo(print())
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.are_friends").value(true));
        }

        @Test
        @DisplayName("친구 여부 확인 - 친구가 아닌 경우")
        void checkFriendship_false() throws Exception {
            // given
            Long userId = 2L;
            given(friendshipService.areFriends(CURRENT_USER_ID, userId)).willReturn(false);

            // when & then
            mockMvc.perform(get("/api/friends/check/{userId}", userId))
                    .andDo(print())
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.are_friends").value(false));
        }
    }
}
