package com.bigtech.chat.friend.controller;

import com.bigtech.chat.common.security.CurrentUser;
import com.bigtech.chat.common.security.JwtPayload;
import com.bigtech.chat.friend.dto.*;
import com.bigtech.chat.friend.entity.Friendship;
import com.bigtech.chat.friend.service.FriendshipService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

/**
 * 친구 관계 컨트롤러
 */
@RestController
@RequestMapping("/api/friends")
@RequiredArgsConstructor
@Tag(name = "Friends", description = "친구 관리 API")
public class FriendController {

    private final FriendshipService friendshipService;

    @PostMapping("/request")
    @Operation(summary = "친구 요청 전송")
    public ResponseEntity<FriendshipResponse> sendFriendRequest(
            @CurrentUser JwtPayload currentUser,
            @Valid @RequestBody FriendshipCreateRequest request) {
        Friendship friendship = friendshipService.sendFriendRequest(
                currentUser.getUserId(),
                currentUser.getUsername(),
                request.getUserId2()
        );
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(FriendshipResponse.from(friendship));
    }

    @PutMapping("/status/{requesterUserId}")
    @Operation(summary = "친구 요청 수락/거절")
    public ResponseEntity<FriendshipResponse> updateFriendRequestStatus(
            @CurrentUser JwtPayload currentUser,
            @PathVariable Long requesterUserId,
            @Valid @RequestBody FriendshipStatusUpdateRequest request) {

        if ("accept".equals(request.getAction())) {
            Friendship friendship = friendshipService.acceptFriendRequest(
                    requesterUserId,
                    currentUser.getUserId(),
                    currentUser.getUsername()
            );
            return ResponseEntity.ok(FriendshipResponse.from(friendship));
        } else {
            friendshipService.rejectFriendRequest(
                    requesterUserId,
                    currentUser.getUserId()
            );
            return ResponseEntity.ok().build();
        }
    }

    @GetMapping("/list")
    @Operation(summary = "친구 목록 조회")
    public ResponseEntity<List<FriendListResponse>> getFriendsList(
            @CurrentUser JwtPayload currentUser) {
        List<FriendListResponse> friends = friendshipService.getFriendsList(
                currentUser.getUserId()
        );
        return ResponseEntity.ok(friends);
    }

    @GetMapping("/requests")
    @Operation(summary = "친구 요청 목록 조회")
    public ResponseEntity<List<FriendRequestListResponse>> getFriendRequests(
            @CurrentUser JwtPayload currentUser) {
        List<FriendRequestListResponse> requests = friendshipService.getFriendRequests(
                currentUser.getUserId()
        );
        return ResponseEntity.ok(requests);
    }

    @DeleteMapping("/request/{targetUserId}")
    @Operation(summary = "친구 요청 취소")
    public ResponseEntity<Map<String, String>> cancelFriendRequest(
            @CurrentUser JwtPayload currentUser,
            @PathVariable Long targetUserId) {
        friendshipService.cancelFriendRequest(
                currentUser.getUserId(),
                targetUserId
        );
        return ResponseEntity.ok(Map.of(
                "message", "Friend request cancelled"
        ));
    }

    @GetMapping("/check/{userId}")
    @Operation(summary = "친구 여부 확인")
    public ResponseEntity<Map<String, Boolean>> checkFriendship(
            @CurrentUser JwtPayload currentUser,
            @PathVariable Long userId) {
        boolean areFriends = friendshipService.areFriends(
                currentUser.getUserId(),
                userId
        );
        return ResponseEntity.ok(Map.of("are_friends", areFriends));
    }
}
