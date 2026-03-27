package com.example.demo.unit.service;

import com.example.demo.service.EmailService;
import jakarta.mail.MessagingException;
import jakarta.mail.internet.MimeMessage;
import org.junit.jupiter.api.*;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.*;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.mail.javamail.JavaMailSender;
import org.springframework.test.util.ReflectionTestUtils;

import java.util.Map;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.BDDMockito.*;

@ExtendWith(MockitoExtension.class)
@DisplayName("EmailService Tests")
class EmailServiceTest {

    @Mock JavaMailSender mailSender;
    @Mock MimeMessage    mimeMessage;

    @InjectMocks EmailService emailService;

    @BeforeEach
    void setUp() throws MessagingException {
        ReflectionTestUtils.setField(emailService, "fromEmail", "noreply@test.com");
        ReflectionTestUtils.setField(emailService, "appName",   "TestApp");
        ReflectionTestUtils.setField(emailService, "appUrl",    "https://test.app");

        given(mailSender.createMimeMessage()).willReturn(mimeMessage);
        // Allow setting recipients, etc. without error
        willDoNothing().given(mailSender).send(any(MimeMessage.class));
    }

    @Test
    @DisplayName("sendWelcomeEmail - calls mailSender.send once")
    void sendWelcomeEmail_callsSendOnce() {
        emailService.sendWelcomeEmail("user@test.com", "Test User", "TempPass123!");

        then(mailSender).should(times(1)).send(any(MimeMessage.class));
    }

    @Test
    @DisplayName("sendWelcomeEmail - SMTP failure throws ExternalServiceException")
    void sendWelcomeEmail_smtpFailure() throws MessagingException {
        willThrow(new RuntimeException("SMTP down")).given(mailSender).send(any(MimeMessage.class));

        assertThatThrownBy(() ->
            emailService.sendWelcomeEmail("user@test.com", "User", "Pass"))
            .isInstanceOf(com.example.demo.exception.ExternalServiceException.class)
            .hasMessageContaining("SMTP");
    }

    @Test
    @DisplayName("sendPasswordChangeConfirmation - calls mailSender.send once")
    void sendPasswordChangeConfirmation_callsSend() {
        emailService.sendPasswordChangeConfirmation("user@test.com", "User", "reset-token-uuid");

        then(mailSender).should(times(1)).send(any(MimeMessage.class));
    }

    @Test
    @DisplayName("sendPasswordChangedNotification - calls mailSender.send once")
    void sendPasswordChangedNotification_callsSend() {
        emailService.sendPasswordChangedNotification("user@test.com", "User");

        then(mailSender).should(times(1)).send(any(MimeMessage.class));
    }

    @Test
    @DisplayName("sendWelcomeBatch - sends all emails, does not stop on individual failure")
    void sendWelcomeBatch_partialFailure_continuesOtherEmails() throws Exception {
        var emailToPassword = Map.of(
            "user1@test.com", "Pass1!",
            "user2@test.com", "Pass2!",
            "user3@test.com", "Pass3!"
        );
        var emailToName = Map.of(
            "user1@test.com", "User 1",
            "user2@test.com", "User 2",
            "user3@test.com", "User 3"
        );

        // Simulate user2's email fails
        var callCount = new AtomicInteger(0);
        willAnswer(inv -> {
            if (callCount.incrementAndGet() == 2) {
                throw new RuntimeException("user2 SMTP error");
            }
            return null;
        }).given(mailSender).send(any(MimeMessage.class));

        CompletableFuture<Void> future = emailService.sendWelcomeBatch(emailToPassword, emailToName);

        // Should complete (not fail the whole batch)
        assertThatCode(() -> future.get(5, TimeUnit.SECONDS)).doesNotThrowAnyException();
    }

    @Test
    @DisplayName("sendWelcomeBatch - empty map completes immediately")
    void sendWelcomeBatch_emptyMap_completesImmediately() throws Exception {
        CompletableFuture<Void> future = emailService.sendWelcomeBatch(Map.of(), Map.of());

        assertThatCode(() -> future.get(3, TimeUnit.SECONDS)).doesNotThrowAnyException();
        then(mailSender).should(never()).send(any(MimeMessage.class));
    }

    @Test
    @DisplayName("sendWelcomeEmailAsync - returns non-null CompletableFuture")
    void sendWelcomeEmailAsync_returnsCompletableFuture() {
        CompletableFuture<Void> future = emailService.sendWelcomeEmailAsync(
            "user@test.com", "User", "Pass");

        assertThat(future).isNotNull();
    }

    @Test
    @DisplayName("sendPasswordChangeConfirmationAsync - returns CompletableFuture")
    void sendPasswordChangeConfirmationAsync_returnsCompletableFuture() {
        CompletableFuture<Void> future = emailService.sendPasswordChangeConfirmationAsync(
            "user@test.com", "User", "token-123");

        assertThat(future).isNotNull();
    }

    @Test
    @DisplayName("sendWelcomeEmail - thread-safe when called by multiple threads simultaneously")
    void sendWelcomeEmail_threadSafe() throws InterruptedException {
        int threadCount    = 20;
        var latch          = new CountDownLatch(1);
        var successCount   = new AtomicInteger(0);
        var executor       = Executors.newFixedThreadPool(threadCount);

        for (int i = 0; i < threadCount; i++) {
            final int idx = i;
            executor.submit(() -> {
                try {
                    latch.await();
                    emailService.sendWelcomeEmail(
                        "user" + idx + "@test.com", "User" + idx, "Password" + idx + "!");
                    successCount.incrementAndGet();
                } catch (Exception e) { /* log */ }
            });
        }

        latch.countDown();
        executor.shutdown();
        executor.awaitTermination(10, TimeUnit.SECONDS);

        assertThat(successCount.get()).isEqualTo(threadCount);
        then(mailSender).should(times(threadCount)).send(any(MimeMessage.class));
    }
}
