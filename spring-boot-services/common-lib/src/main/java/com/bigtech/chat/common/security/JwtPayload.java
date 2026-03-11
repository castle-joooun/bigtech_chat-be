package com.bigtech.chat.common.security;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.Date;

/**
 * JWT 토큰 페이로드
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class JwtPayload {

    private Long userId;
    private String email;
    private String username;
    private Date expiration;

    public boolean isExpired() {
        return expiration != null && expiration.before(new Date());
    }
}
