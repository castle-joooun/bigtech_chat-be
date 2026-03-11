package com.bigtech.chat.common.client;

import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * Batch 사용자 조회 요청 DTO
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class UserBatchRequest {
    private List<Long> userIds;

    public static UserBatchRequest of(List<Long> userIds) {
        return new UserBatchRequest(userIds);
    }
}
