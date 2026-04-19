package com.example.demo.service.auth;

import com.example.demo.dto.auth.BulkRegisterRequest;
import com.example.demo.dto.auth.LoginRequest;
import com.example.demo.exception.BadRequestException;
import com.example.demo.exception.DuplicateResourceException;
import com.example.demo.enums.UserRole;
import com.example.demo.model.User;
import com.example.demo.repository.UserRepository;
import com.example.demo.service.email.EmailService;
import com.example.demo.service.user.UserSyncService;
import com.example.demo.strategy.RoleResolutionStrategy;
import com.example.demo.utils.PasswordGenerator;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class AuthService {

    private final UserRepository userRepository;
    private final JwtService jwtService;
    private final PasswordEncoder passwordEncoder;
    private final EmailService emailService;
    private final UserSyncService userSyncService;
    private final RoleResolutionStrategy roleStrategy;

    public User authenticate(LoginRequest request) {
        var user = userRepository.findByEmail(request.getEmail())
                .orElseThrow(() -> new BadRequestException("Invalid email or password"));

        if (!passwordEncoder.matches(request.getPassword(), user.getPassword())) {
            throw new BadRequestException("Invalid email or password");
        }

        if (!user.getActive()) {
            throw new BadRequestException("Tài khoản của bạn đã bị khóa. Vui lòng liên hệ quản trị viên.");
        }

        return user;
    }

    public String generateToken(User user) {
        return jwtService.generateToken(user.getId(), user.getEmail(),
                                        roleStrategy.resolve(user.getRole()));
    }

    public String generateRefreshToken(User user) {
        return jwtService.generateRefreshToken(user.getId(), user.getEmail());
    }

    public boolean validateToken(String token) {
        return jwtService.validateToken(token);
    }

    public String extractEmail(String token) {
        return jwtService.extractEmail(token);
    }

    @Transactional
    public List<User> bulkRegister(BulkRegisterRequest request) {
        var registrations = request.getUsers();

        // 1. Validate trước: collect tất cả duplicate email
        var duplicates = registrations.stream()
                .map(r -> r.getEmail())
                .filter(userRepository::existsByEmail)
                .toList();

        if (!duplicates.isEmpty()) {
            throw new DuplicateResourceException("User", "email", String.join(", ", duplicates));
        }

        Map<String, String> emailToPassword = new java.util.LinkedHashMap<>();
        Map<String, String> emailToName    = new java.util.LinkedHashMap<>();

        List<User> users = registrations.stream()
                .map(reg -> {
                    String pwd = PasswordGenerator.generateStrongPassword();
                    emailToPassword.put(reg.getEmail(), pwd);
                    emailToName.put(reg.getEmail(), reg.getName());
                    return User.builder()
                            .name(reg.getName())
                            .email(reg.getEmail())
                            .password(passwordEncoder.encode(pwd))
                            .role(reg.getRole() != null ? reg.getRole() : UserRole.ROLE_USER)
                            .team(reg.getTeam())
                            .code(reg.getCode())
                            .type(reg.getType())
                            .active(true)
                            .totalScore(0)
                            .build();
                })
                .collect(Collectors.toList());

        List<User> saved = userRepository.saveAll(users);
        log.info("Bulk registered {} users", saved.size());

        emailService.sendWelcomeBatch(emailToPassword, emailToName)
                    .exceptionally(ex -> { log.error("Batch email error: {}", ex.getMessage()); return null; });

        userSyncService.syncUsers(saved)
                       .exceptionally(ex -> { log.error("LMS sync error: {}", ex.getMessage()); return null; });

        return saved;
    }
}