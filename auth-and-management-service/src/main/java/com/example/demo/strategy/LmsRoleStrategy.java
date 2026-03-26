package com.example.demo.strategy;

import com.example.demo.enums.UserRole;

import java.util.Map;
import java.util.List;

@org.springframework.stereotype.Component
class LmsRoleStrategy implements RoleResolutionStrategy {

    private static final Map<UserRole, List<String>> ROLE_MAP = Map.of(
        UserRole.ROLE_ADMIN,   List.of("TEACHER", "STUDENT", "ADMIN"),
        UserRole.ROLE_MANAGER, List.of("TEACHER", "STUDENT", "MANAGER"),
        UserRole.ROLE_USER,    List.of("TEACHER", "STUDENT")
    );

    @Override
    public List<String> resolve(UserRole role) {
        return ROLE_MAP.getOrDefault(role, List.of("STUDENT"));
    }
}
