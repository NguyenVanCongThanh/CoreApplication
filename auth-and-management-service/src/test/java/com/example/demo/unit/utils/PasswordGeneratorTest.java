package com.example.demo.unit.utils;

import com.example.demo.utils.PasswordGenerator;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

import java.util.HashSet;
import java.util.Set;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

import static org.assertj.core.api.Assertions.*;

@DisplayName("PasswordGenerator Tests")
class PasswordGeneratorTest {

    @Test
    @DisplayName("generateStrongPassword - default length is 12")
    void defaultLength_is12() {
        assertThat(PasswordGenerator.generateStrongPassword()).hasSize(12);
    }

    @ParameterizedTest
    @ValueSource(ints = {8, 10, 16, 20, 50})
    @DisplayName("generateStrongPassword - respects custom length")
    void customLength_respected(int length) {
        assertThat(PasswordGenerator.generateStrongPassword(length)).hasSize(length);
    }

    @Test
    @DisplayName("generateStrongPassword - contains uppercase, lowercase, digit, special")
    void passwordMeetsStrengthRequirements() {
        // Run 50 times to reduce flakiness from randomness
        for (int i = 0; i < 50; i++) {
            String pwd = PasswordGenerator.generateStrongPassword();
            assertThat(pwd.chars().anyMatch(Character::isUpperCase)).isTrue();
            assertThat(pwd.chars().anyMatch(Character::isLowerCase)).isTrue();
            assertThat(pwd.chars().anyMatch(Character::isDigit)).isTrue();
            assertThat(pwd).containsAnyOf("!", "@", "#", "$", "%", "^", "&", "*", "(", ")");
        }
    }

    @Test
    @DisplayName("generateStrongPassword - length < 8 throws IllegalArgumentException")
    void tooShort_throws() {
        assertThatThrownBy(() -> PasswordGenerator.generateStrongPassword(7))
            .isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    @DisplayName("generateStrongPassword - produces unique passwords (randomness)")
    void producesUniquePasswords() {
        Set<String> passwords = new HashSet<>();
        for (int i = 0; i < 100; i++) {
            passwords.add(PasswordGenerator.generateStrongPassword());
        }
        // Very unlikely to have duplicates with strong random; expect >= 95 unique
        assertThat(passwords.size()).isGreaterThanOrEqualTo(95);
    }

    @Test
    @DisplayName("generateStrongPassword - thread-safe under concurrent access (ThreadLocal SecureRandom)")
    void threadSafe_concurrentAccess() throws InterruptedException {
        int threadCount  = 50;
        var latch        = new CountDownLatch(1);
        var successCount = new AtomicInteger(0);
        var errorCount   = new AtomicInteger(0);
        var executor     = Executors.newFixedThreadPool(threadCount);
        var passwords    = new ConcurrentHashMap<String, Boolean>();

        for (int i = 0; i < threadCount; i++) {
            executor.submit(() -> {
                try {
                    latch.await();
                    String pwd = PasswordGenerator.generateStrongPassword();
                    assertThat(pwd).hasSize(12);
                    passwords.put(pwd, true);
                    successCount.incrementAndGet();
                } catch (Exception e) {
                    errorCount.incrementAndGet();
                }
            });
        }

        latch.countDown();
        executor.shutdown();
        executor.awaitTermination(10, TimeUnit.SECONDS);

        assertThat(errorCount.get()).isZero();
        assertThat(successCount.get()).isEqualTo(threadCount);
    }
}