package com.bigtech.chat.user.controller;

import com.bigtech.chat.common.security.CurrentUser;
import com.bigtech.chat.common.security.JwtPayload;
import com.bigtech.chat.user.dto.UserBatchRequest;
import com.bigtech.chat.user.dto.UserExistsResponse;
import com.bigtech.chat.user.dto.UserProfileResponse;
import com.bigtech.chat.user.dto.UserSearchResponse;
import com.bigtech.chat.user.entity.User;
import com.bigtech.chat.user.service.UserSearchService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.stream.Collectors;

/**
 * 사용자 컨트롤러
 */
@RestController
@RequestMapping("/api/users")
@RequiredArgsConstructor
@Tag(name = "Users", description = "사용자 관리 API")
public class UserController {

    private final UserSearchService userSearchService;

    @GetMapping("/search")
    @Operation(summary = "사용자 검색")
    public ResponseEntity<List<UserSearchResponse>> searchUsers(
            @CurrentUser JwtPayload currentUser,
            @RequestParam String query,
            @RequestParam(defaultValue = "20") int limit) {
        List<UserSearchResponse> users = userSearchService.searchUsers(
                query,
                currentUser.getUserId(),
                limit
        );
        return ResponseEntity.ok(users);
    }

    @GetMapping("/{userId}")
    @Operation(summary = "사용자 조회")
    public ResponseEntity<UserProfileResponse> getUser(
            @PathVariable Long userId) {
        User user = userSearchService.findById(userId);
        return ResponseEntity.ok(UserProfileResponse.from(user));
    }

    /**
     * Batch 사용자 조회 (서비스 간 통신용)
     *
     * friend-service, chat-service에서 여러 사용자 정보를 한 번에 조회할 때 사용
     */
    @PostMapping("/batch")
    @Operation(summary = "다중 사용자 일괄 조회", description = "서비스 간 통신용 - 여러 사용자 ID로 일괄 조회")
    public ResponseEntity<List<UserProfileResponse>> getUsersBatch(
            @Valid @RequestBody UserBatchRequest request) {
        List<User> users = userSearchService.findAllByIds(request.getUserIds());
        List<UserProfileResponse> response = users.stream()
                .map(UserProfileResponse::from)
                .collect(Collectors.toList());
        return ResponseEntity.ok(response);
    }

    /**
     * 사용자 존재 여부 확인 (서비스 간 통신용)
     */
    @GetMapping("/{userId}/exists")
    @Operation(summary = "사용자 존재 여부 확인", description = "서비스 간 통신용 - 사용자 존재 여부 확인")
    public ResponseEntity<UserExistsResponse> checkUserExists(
            @PathVariable Long userId) {
        boolean exists = userSearchService.existsById(userId);
        return ResponseEntity.ok(UserExistsResponse.of(userId, exists));
    }
}
