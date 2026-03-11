package com.bigtech.chat.common.client;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 사용자 존재 여부 응답 DTO
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class UserExistsResponse {
    private Long userId;
    private Boolean exists;
}
