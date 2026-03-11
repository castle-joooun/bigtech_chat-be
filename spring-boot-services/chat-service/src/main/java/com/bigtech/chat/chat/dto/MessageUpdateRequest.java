package com.bigtech.chat.chat.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 메시지 수정 요청 DTO
 *
 * FastAPI의 MessageCreate 스키마와 동일한 검증 규칙을 적용합니다.
 * MessageCreateRequest와 동일하게 1-300자 제한.
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MessageUpdateRequest {

    @NotBlank(message = "수정할 메시지 내용은 필수입니다")
    @Size(min = 1, max = 300, message = "메시지는 1-300자 사이여야 합니다")
    private String content;
}
