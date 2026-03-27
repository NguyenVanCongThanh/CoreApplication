package com.example.demo.unit.strategy;

import com.example.demo.enums.UserRole;
import com.example.demo.strategy.LmsRoleStrategy;
import com.example.demo.strategy.RoleResolutionStrategy;
import org.junit.jupiter.api.*;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.EnumSource;

import static org.assertj.core.api.Assertions.*;

@DisplayName("LmsRoleStrategy Tests")
class LmsRoleStrategyTest {

    private final RoleResolutionStrategy strategy = new LmsRoleStrategy();

    @Test
    @DisplayName("ROLE_ADMIN - gets TEACHER, STUDENT, ADMIN")
    void admin_getsAllThreeRoles() {
        assertThat(strategy.resolve(UserRole.ROLE_ADMIN))
            .containsExactlyInAnyOrder("TEACHER", "STUDENT", "ADMIN");
    }

    @Test
    @DisplayName("ROLE_MANAGER - gets TEACHER, STUDENT, MANAGER")
    void manager_getsManagerRole() {
        assertThat(strategy.resolve(UserRole.ROLE_MANAGER))
            .containsExactlyInAnyOrder("TEACHER", "STUDENT", "MANAGER");
    }

    @Test
    @DisplayName("ROLE_USER - gets TEACHER and STUDENT only")
    void user_getsBaseRolesOnly() {
        assertThat(strategy.resolve(UserRole.ROLE_USER))
            .containsExactlyInAnyOrder("TEACHER", "STUDENT")
            .doesNotContain("ADMIN", "MANAGER");
    }

    @ParameterizedTest
    @EnumSource(UserRole.class)
    @DisplayName("All roles - always include TEACHER and STUDENT")
    void allRoles_alwaysIncludeBaseRoles(UserRole role) {
        assertThat(strategy.resolve(role))
            .contains("TEACHER", "STUDENT");
    }

    @Test
    @DisplayName("Returned list is immutable (thread-safe)")
    void returnedList_isImmutable() {
        var roles = strategy.resolve(UserRole.ROLE_USER);
        assertThatThrownBy(() -> roles.add("HACKER"))
            .isInstanceOf(UnsupportedOperationException.class);
    }
}
