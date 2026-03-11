package com.bigtech.chat.chat.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;

/**
 * 메시지 생성 요청 DTO
 *
 * FastAPI와 동일한 message_type 검증:
 * 허용 타입: text, image, file, system
 */
@Data
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class MessageCreateRequest {

    @NotBlank(message = "메시지 내용은 필수입니다")
    @Size(min = 1, max = 300, message = "메시지는 1-300자 사이여야 합니다")
    private String content;

    @Builder.Default
    @Pattern(regexp = "^(text|image|file|system)$", message = "messageType은 text, image, file, system 중 하나여야 합니다")
    private String messageType = "text";
}
