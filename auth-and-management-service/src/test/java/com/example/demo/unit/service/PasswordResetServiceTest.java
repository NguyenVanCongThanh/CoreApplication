package com.example.demo.unit.service;

import com.example.demo.common.TestDataFactory;
import com.example.demo.exception.InvalidTokenException;
import com.example.demo.model.User;
import com.example.demo.repository.PasswordResetTokenRepository;
import com.example.demo.service.user.PasswordResetService;

import org.junit.jupiter.api.*;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.*;
import org.mockito.junit.jupiter.MockitoExtension;

import java.time.LocalDateTime;
import java.util.Optional;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.BDDMockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("PasswordResetService Tests")
class PasswordResetServiceTest {

    @Mock PasswordResetTokenRepository tokenRepository;

    @InjectMocks PasswordResetService passwordResetService;

    private User user;

    @BeforeEach
    void setUp() {
        user = TestDataFactory.regularUser();
    }

    @Test
    @DisplayName("createToken - deletes existing token before creating new one")
    void createToken_deletesOldFirst() {
        given(tokenRepository.save(any())).willReturn(TestDataFactory.validToken(user));

        passwordResetService.createToken(user);

        then(tokenRepository).should().deleteByUser(user);
        then(tokenRepository).should().save(argThat(t ->
            !t.isUsed() &&
            t.getToken() != null &&
            t.getExpiryDate().isAfter(LocalDateTime.now()) &&
            t.getUser().equals(user)
        ));
    }

    @Test
    @DisplayName("createToken - generates unique UUID token each call")
    void createToken_generatesUniqueToken() {
        var token1 = TestDataFactory.validToken(user);
        var token2 = TestDataFactory.validToken(user);
        token2.setToken("different-uuid");

        given(tokenRepository.save(any())).willReturn(token1, token2);

        then(tokenRepository).should(times(2)).deleteByUser(user);
    }

    @Test
    @DisplayName("validateAndGetToken - valid token returns token entity")
    void validateAndGetToken_valid() {
        var token = TestDataFactory.validToken(user);
        given(tokenRepository.findByToken("valid-reset-token-uuid")).willReturn(Optional.of(token));

        var result = passwordResetService.validateAndGetToken("valid-reset-token-uuid");

        assertThat(result).isEqualTo(token);
    }

    @Test
    @DisplayName("validateAndGetToken - non-existent token throws InvalidTokenException")
    void validateAndGetToken_notFound() {
        given(tokenRepository.findByToken("ghost-token")).willReturn(Optional.empty());

        assertThatThrownBy(() -> passwordResetService.validateAndGetToken("ghost-token"))
            .isInstanceOf(InvalidTokenException.class)
            .hasMessageContaining("does not exist");
    }

    @Test
    @DisplayName("validateAndGetToken - already used token throws InvalidTokenException")
    void validateAndGetToken_alreadyUsed() {
        var token = TestDataFactory.usedToken(user);
        given(tokenRepository.findByToken("used-token")).willReturn(Optional.of(token));

        assertThatThrownBy(() -> passwordResetService.validateAndGetToken("used-token"))
            .isInstanceOf(InvalidTokenException.class)
            .hasMessageContaining("already been used");
    }

    @Test
    @DisplayName("validateAndGetToken - expired token throws InvalidTokenException")
    void validateAndGetToken_expired() {
        var token = TestDataFactory.expiredToken(user);
        given(tokenRepository.findByToken("expired-token")).willReturn(Optional.of(token));

        assertThatThrownBy(() -> passwordResetService.validateAndGetToken("expired-token"))
            .isInstanceOf(InvalidTokenException.class)
            .hasMessageContaining("expired");
    }

    @Test
    @DisplayName("markTokenAsUsed - sets used=true and saves")
    void markTokenAsUsed_setsUsedTrue() {
        var token = TestDataFactory.validToken(user);
        assertThat(token.isUsed()).isFalse();

        passwordResetService.markTokenAsUsed(token);

        assertThat(token.isUsed()).isTrue();
        then(tokenRepository).should().save(token);
    }

    @Test
    @DisplayName("cleanupExpiredTokens - calls deleteByExpiryDateBefore with current time")
    void cleanupExpiredTokens_callsRepository() {
        passwordResetService.cleanupExpiredTokens();

        then(tokenRepository).should().deleteByExpiryDateBefore(any(LocalDateTime.class));
    }
}
