package com.example.demo.strategy;

import com.example.demo.enums.UserRole;

import java.util.List;

public interface RoleResolutionStrategy {
    List<String> resolve(UserRole role);
}