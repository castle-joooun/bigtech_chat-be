package com.bigtech.chat.chat.controller;

import com.bigtech.chat.chat.dto.ChatRoomResponse;
import com.bigtech.chat.chat.dto.MessageResponse;
import com.bigtech.chat.chat.entity.ChatRoom;
import com.bigtech.chat.chat.service.ChatRoomService;
import com.bigtech.chat.common.exception.BusinessLogicException;
import com.bigtech.chat.common.exception.ErrorCode;
import com.bigtech.chat.common.exception.GlobalExceptionHandler;
import com.bigtech.chat.common.exception.ResourceNotFoundException;
import com.bigtech.chat.common.security.JwtPayload;
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
import java.util.Map;

import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.BDDMockito.given;
import static org.mockito.Mockito.doNothing;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.verify;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultHandlers.print;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

/**
 * ChatRoomController API Test
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("ChatRoomController API Test")
class ChatRoomControllerTest {

    private MockMvc mockMvc;

    @Mock
    private ChatRoomService chatRoomService;

    @InjectMocks
    private ChatRoomController chatRoomController;

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
                .standaloneSetup(chatRoomController)
                .setControllerAdvice(new GlobalExceptionHandler())
                .setCustomArgumentResolvers(currentUserResolver)
                .build();
    }

    @Nested
    @DisplayName("GET /api/chat-rooms")
    class GetChatRoomsTest {

        @Test
        @DisplayName("채팅방 목록 조회 성공 - 200 OK")
        void getChatRooms_success() throws Exception {
            // given
            List<ChatRoomResponse> rooms = Arrays.asList(
                    ChatRoomResponse.builder()
                            .id(1L)
                            .user1Id(CURRENT_USER_ID)
                            .user2Id(2L)
                            .roomType("direct")
                            .participants(List.of(
                                    Map.of("id", CURRENT_USER_ID, "username", CURRENT_USER_USERNAME),
                                    Map.of("id", 2L, "username", "user2")
                            ))
                            .createdAt(LocalDateTime.now())
                            .build(),
                    ChatRoomResponse.builder()
                            .id(2L)
                            .user1Id(CURRENT_USER_ID)
                            .user2Id(3L)
                            .roomType("direct")
                            .participants(List.of(
                                    Map.of("id", CURRENT_USER_ID, "username", CURRENT_USER_USERNAME),
                                    Map.of("id", 3L, "username", "user3")
                            ))
                            .createdAt(LocalDateTime.now())
                            .build()
            );

            given(chatRoomService.getChatRooms(CURRENT_USER_ID, 0, 10)).willReturn(rooms);

            // when & then
            mockMvc.perform(get("/api/chat-rooms"))
                    .andDo(print())
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.length()").value(2))
                    .andExpect(jsonPath("$[0].id").value(1L))
                    .andExpect(jsonPath("$[0].user2Id").value(2L))
                    .andExpect(jsonPath("$[1].id").value(2L));

            verify(chatRoomService).getChatRooms(CURRENT_USER_ID, 0, 10);
        }

        @Test
        @DisplayName("채팅방 목록 조회 - 채팅방 없음 - 200 OK")
        void getChatRooms_empty() throws Exception {
            // given
            given(chatRoomService.getChatRooms(CURRENT_USER_ID, 0, 10)).willReturn(Collections.emptyList());

            // when & then
            mockMvc.perform(get("/api/chat-rooms"))
                    .andDo(print())
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.length()").value(0));
        }
    }

    @Nested
    @DisplayName("GET /api/chat-rooms/check/{targetUserId}")
    class GetOrCreateChatRoomTest {

        @Test
        @DisplayName("채팅방 조회/생성 성공 (새 채팅방) - 200 OK")
        void getOrCreateChatRoom_create() throws Exception {
            // given
            Long targetUserId = 2L;

            ChatRoomResponse room = ChatRoomResponse.builder()
                    .id(1L)
                    .user1Id(CURRENT_USER_ID)
                    .user2Id(targetUserId)
                    .roomType("direct")
                    .participants(List.of(
                            Map.of("id", CURRENT_USER_ID, "username", CURRENT_USER_USERNAME),
                            Map.of("id", targetUserId, "username", "user2")
                    ))
                    .createdAt(LocalDateTime.now())
                    .build();

            given(chatRoomService.getOrCreateChatRoom(CURRENT_USER_ID, targetUserId)).willReturn(room);

            // when & then
            mockMvc.perform(get("/api/chat-rooms/check/{targetUserId}", targetUserId))
                    .andDo(print())
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.id").value(1L))
                    .andExpect(jsonPath("$.user2Id").value(targetUserId))
                    .andExpect(jsonPath("$.roomType").value("direct"));

            verify(chatRoomService).getOrCreateChatRoom(CURRENT_USER_ID, targetUserId);
        }

        @Test
        @DisplayName("채팅방 조회/생성 실패 - 자기 자신 (400 Bad Request)")
        void getOrCreateChatRoom_fail_self() throws Exception {
            // given
            given(chatRoomService.getOrCreateChatRoom(CURRENT_USER_ID, CURRENT_USER_ID))
                    .willThrow(new BusinessLogicException(ErrorCode.CANNOT_CHAT_SELF));

            // when & then
            mockMvc.perform(get("/api/chat-rooms/check/{targetUserId}", CURRENT_USER_ID))
                    .andDo(print())
                    .andExpect(status().isUnprocessableEntity())
                    .andExpect(jsonPath("$.error").value("CANNOT_CHAT_SELF"));
        }

        @Test
        @DisplayName("채팅방 조회/생성 실패 - 사용자 없음 (404 Not Found)")
        void getOrCreateChatRoom_fail_userNotFound() throws Exception {
            // given
            Long targetUserId = 999L;

            given(chatRoomService.getOrCreateChatRoom(CURRENT_USER_ID, targetUserId))
                    .willThrow(new ResourceNotFoundException(ErrorCode.USER_NOT_FOUND));

            // when & then
            mockMvc.perform(get("/api/chat-rooms/check/{targetUserId}", targetUserId))
                    .andDo(print())
                    .andExpect(status().isNotFound())
                    .andExpect(jsonPath("$.error").value("USER_NOT_FOUND"));
        }
    }

    @Nested
    @DisplayName("GET /api/chat-rooms/{roomId}")
    class GetChatRoomDetailTest {

        @Test
        @DisplayName("채팅방 상세 조회 성공 - 200 OK")
        void getChatRoomDetail_success() throws Exception {
            // given
            Long roomId = 1L;

            ChatRoomResponse roomResponse = ChatRoomResponse.builder()
                    .id(roomId)
                    .user1Id(CURRENT_USER_ID)
                    .user2Id(2L)
                    .roomType("direct")
                    .participants(List.of(
                            Map.of("id", CURRENT_USER_ID, "username", CURRENT_USER_USERNAME),
                            Map.of("id", 2L, "username", "user2")
                    ))
                    .createdAt(LocalDateTime.now())
                    .updatedAt(LocalDateTime.now())
                    .build();

            given(chatRoomService.getChatRoomDetail(roomId, CURRENT_USER_ID)).willReturn(roomResponse);

            // when & then
            mockMvc.perform(get("/api/chat-rooms/{roomId}", roomId))
                    .andDo(print())
                    .andExpect(status().isOk())
                    .andExpect(jsonPath("$.id").value(roomId));

            verify(chatRoomService).getChatRoomDetail(roomId, CURRENT_USER_ID);
        }

        @Test
        @DisplayName("채팅방 상세 조회 실패 - 권한 없음 (403 Forbidden)")
        void getChatRoomDetail_fail_accessDenied() throws Exception {
            // given
            Long roomId = 1L;

            given(chatRoomService.getChatRoomDetail(roomId, CURRENT_USER_ID))
                    .willThrow(new BusinessLogicException(ErrorCode.CHATROOM_ACCESS_DENIED));

            // when & then
            mockMvc.perform(get("/api/chat-rooms/{roomId}", roomId))
                    .andDo(print())
                    .andExpect(status().isForbidden())
                    .andExpect(jsonPath("$.error").value("CHATROOM_ACCESS_DENIED"));
        }

        @Test
        @DisplayName("채팅방 상세 조회 실패 - 채팅방 없음 (404 Not Found)")
        void getChatRoomDetail_fail_notFound() throws Exception {
            // given
            Long roomId = 999L;

            given(chatRoomService.getChatRoomDetail(roomId, CURRENT_USER_ID))
                    .willThrow(new ResourceNotFoundException(ErrorCode.CHATROOM_NOT_FOUND));

            // when & then
            mockMvc.perform(get("/api/chat-rooms/{roomId}", roomId))
                    .andDo(print())
                    .andExpect(status().isNotFound())
                    .andExpect(jsonPath("$.error").value("CHATROOM_NOT_FOUND"));
        }
    }
}
