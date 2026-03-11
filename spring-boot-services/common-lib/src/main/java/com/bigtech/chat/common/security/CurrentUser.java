package com.bigtech.chat.common.security;

import java.lang.annotation.*;

/**
 * 현재 인증된 사용자를 주입받는 어노테이션
 *
 * 사용 예시:
 * @GetMapping("/profile/me")
 * public ResponseEntity<?> getMyProfile(@CurrentUser JwtPayload currentUser) {
 *     // currentUser.getUserId(), currentUser.getEmail() 등 사용
 * }
 */
@Target(ElementType.PARAMETER)
@Retention(RetentionPolicy.RUNTIME)
@Documented
public @interface CurrentUser {
}
