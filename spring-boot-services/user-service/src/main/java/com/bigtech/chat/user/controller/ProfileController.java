package com.bigtech.chat.user.controller;

import com.bigtech.chat.common.security.CurrentUser;
import com.bigtech.chat.common.security.JwtPayload;
import com.bigtech.chat.user.dto.ProfileUpdateRequest;
import com.bigtech.chat.user.dto.UserProfileResponse;
import com.bigtech.chat.user.entity.User;
import com.bigtech.chat.user.service.ProfileService;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

/**
 * 프로필 컨트롤러
 */
@RestController
@RequestMapping("/api/profile")
@RequiredArgsConstructor
@Tag(name = "Profile", description = "프로필 관리 API")
public class ProfileController {

    private final ProfileService profileService;

    @GetMapping("/me")
    @Operation(summary = "내 프로필 조회")
    public ResponseEntity<UserProfileResponse> getMyProfile(
            @CurrentUser JwtPayload currentUser) {
        User user = profileService.getProfile(currentUser.getUserId());
        return ResponseEntity.ok(UserProfileResponse.from(user));
    }

    @PutMapping("/me")
    @Operation(summary = "내 프로필 수정")
    public ResponseEntity<UserProfileResponse> updateMyProfile(
            @CurrentUser JwtPayload currentUser,
            @Valid @RequestBody ProfileUpdateRequest request) {
        User user = profileService.updateProfile(currentUser.getUserId(), request);
        return ResponseEntity.ok(UserProfileResponse.from(user));
    }
}
