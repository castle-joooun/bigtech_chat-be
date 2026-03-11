package com.bigtech.chat.common.validation;

import jakarta.validation.ConstraintValidator;
import jakarta.validation.ConstraintValidatorContext;

import java.util.regex.Pattern;

/**
 * 비밀번호 정책 검증기
 *
 * 정책:
 * - 길이: 8-16자
 * - 영문자: 최소 1개
 * - 숫자: 최소 1개
 * - 특수문자: 최소 1개
 */
public class PasswordValidator implements ConstraintValidator<ValidPassword, String> {

    private static final Pattern LETTER_PATTERN = Pattern.compile("[a-zA-Z]");
    private static final Pattern DIGIT_PATTERN = Pattern.compile("\\d");
    private static final Pattern SPECIAL_PATTERN = Pattern.compile("[!\"#$%&'()*+,\\-./:;<=>?@\\[\\]^_`{|}~]");

    @Override
    public void initialize(ValidPassword constraintAnnotation) {
        // 초기화 필요 없음
    }

    @Override
    public boolean isValid(String password, ConstraintValidatorContext context) {
        if (password == null) {
            return false;
        }

        // 길이 검사
        if (password.length() < 8 || password.length() > 16) {
            return false;
        }

        // 영문자 검사
        boolean hasLetter = LETTER_PATTERN.matcher(password).find();

        // 숫자 검사
        boolean hasDigit = DIGIT_PATTERN.matcher(password).find();

        // 특수문자 검사
        boolean hasSpecial = SPECIAL_PATTERN.matcher(password).find();

        return hasLetter && hasDigit && hasSpecial;
    }

    /**
     * 정적 검증 메서드
     */
    public static boolean isValid(String password) {
        if (password == null || password.length() < 8 || password.length() > 16) {
            return false;
        }

        boolean hasLetter = LETTER_PATTERN.matcher(password).find();
        boolean hasDigit = DIGIT_PATTERN.matcher(password).find();
        boolean hasSpecial = SPECIAL_PATTERN.matcher(password).find();

        return hasLetter && hasDigit && hasSpecial;
    }
}
