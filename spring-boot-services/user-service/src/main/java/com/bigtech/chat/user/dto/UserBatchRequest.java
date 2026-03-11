package com.bigtech.chat.user.dto;

import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.NoArgsConstructor;

import java.util.List;

/**
 * Batch 사용자 조회 요청 DTO
 *
 * 서비스 간 통신용 (friend-service, chat-service에서 사용)
 */
@Data
@NoArgsConstructor
@AllArgsConstructor
public class UserBatchRequest {

    @NotEmpty(message = "user_ids는 필수입니다")
    @Size(min = 1, max = 100, message = "user_ids는 1~100개 사이여야 합니다")
    private List<Long> userIds;
}
