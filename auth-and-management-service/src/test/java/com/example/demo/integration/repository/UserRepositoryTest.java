package com.example.demo.integration.repository;

import com.example.demo.enums.*;
import com.example.demo.model.*;
import com.example.demo.repository.*;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.orm.jpa.DataJpaTest;
import org.springframework.test.context.ActiveProfiles;

import java.util.List;

import static org.assertj.core.api.Assertions.*;

@DataJpaTest
@ActiveProfiles("test")
@DisplayName("UserRepository Tests")
class UserRepositoryTest {

    @Autowired UserRepository userRepo;

    private User savedUser;

    @BeforeEach
    void setUp() {
        savedUser = userRepo.save(User.builder()
                .name("Test User").email("test@test.com").password("enc")
                .role(UserRole.ROLE_USER).team(UserTeam.RESEARCH)
                .code("TEST001").type(UserType.DT).active(true).totalScore(0).build());
    }

    @Test
    @DisplayName("findByEmail - returns user when email matches")
    void findByEmail_found() {
        assertThat(userRepo.findByEmail("test@test.com"))
            .isPresent()
            .get()
            .extracting(User::getName)
            .isEqualTo("Test User");
    }

    @Test
    @DisplayName("findByEmail - returns empty when email not found")
    void findByEmail_notFound() {
        assertThat(userRepo.findByEmail("ghost@test.com")).isEmpty();
    }

    @Test
    @DisplayName("existsByEmail - true for existing email")
    void existsByEmail_true() {
        assertThat(userRepo.existsByEmail("test@test.com")).isTrue();
    }

    @Test
    @DisplayName("existsByEmail - false for non-existing email")
    void existsByEmail_false() {
        assertThat(userRepo.existsByEmail("nope@test.com")).isFalse();
    }

    @Test
    @DisplayName("uniqueEmail constraint - cannot save duplicate email")
    void uniqueEmail_constraint() {
        assertThatThrownBy(() -> {
            userRepo.save(User.builder()
                    .name("Dup").email("test@test.com") // same email
                    .password("enc").role(UserRole.ROLE_USER)
                    .team(UserTeam.RESEARCH).code("DUP001")
                    .type(UserType.DT).active(true).totalScore(0).build());
            userRepo.flush();
        }).isInstanceOf(Exception.class);
    }

    @Test
    @DisplayName("saveAll - persists multiple users in one call")
    void saveAll_multipleUsers() {
        var users = List.of(
            User.builder().name("U1").email("u1@test.com").password("enc")
                .role(UserRole.ROLE_USER).team(UserTeam.EVENT).code("U001")
                .type(UserType.TN).active(true).totalScore(0).build(),
            User.builder().name("U2").email("u2@test.com").password("enc")
                .role(UserRole.ROLE_USER).team(UserTeam.MEDIA).code("U002")
                .type(UserType.CLC).active(true).totalScore(0).build()
        );

        var saved = userRepo.saveAll(users);

        assertThat(saved).hasSize(2);
        assertThat(saved).allMatch(u -> u.getId() != null);
    }

    @Test
    @DisplayName("update totalScore - reflects immediately after save")
    void updateTotalScore_reflectsImmediately() {
        savedUser.setTotalScore(500);
        userRepo.save(savedUser);

        var reloaded = userRepo.findById(savedUser.getId()).orElseThrow();
        assertThat(reloaded.getTotalScore()).isEqualTo(500);
    }
}
