package com.example.demo.service;

import com.example.demo.exception.InvalidTokenException;
import com.example.demo.model.PasswordResetToken;
import com.example.demo.model.User;
import com.example.demo.repository.PasswordResetTokenRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.UUID;

/**
 * PasswordResetService - quản lý token đặt lại mật khẩu.
 *
 * Cải tiến:
 * - Typed exception (InvalidTokenException) thay vì RuntimeException("Token đã hết hạn...")
 * - Xóa token cũ trước khi tạo mới trong 1 transaction
 * - cleanupExpiredTokens() chạy scheduler 2h sáng mỗi ngày (không thay đổi)
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class PasswordResetService {

    private static final int EXPIRY_MINUTES = 15;

    private final PasswordResetTokenRepository tokenRepository;

    @Transactional
    public PasswordResetToken createToken(User user) {
        // Xóa token cũ của user này trước (1 user chỉ có 1 pending token)
        tokenRepository.deleteByUser(user);

        var token = PasswordResetToken.builder()
                .token(UUID.randomUUID().toString())
                .user(user)
                .expiryDate(LocalDateTime.now().plusMinutes(EXPIRY_MINUTES))
                .createdAt(LocalDateTime.now())
                .used(false)
                .build();

        return tokenRepository.save(token);
    }

    @Transactional(readOnly = true)
    public PasswordResetToken validateAndGetToken(String tokenValue) {
        var token = tokenRepository.findByToken(tokenValue)
                .orElseThrow(() -> new InvalidTokenException("token does not exist"));

        if (token.isUsed())    throw new InvalidTokenException("token has already been used");
        if (token.isExpired()) throw new InvalidTokenException("token has expired, please request again");

        return token;
    }

    @Transactional
    public void markTokenAsUsed(PasswordResetToken token) {
        token.setUsed(true);
        tokenRepository.save(token);
    }

    /** Dọn token hết hạn - chạy 02:00 mỗi ngày */
    @Scheduled(cron = "0 0 2 * * *")
    @Transactional
    public void cleanupExpiredTokens() {
        tokenRepository.deleteByExpiryDateBefore(LocalDateTime.now());
        log.info("Cleaned up expired password reset tokens");
    }
}