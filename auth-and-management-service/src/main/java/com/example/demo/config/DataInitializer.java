package com.example.demo.config;

import com.example.demo.enums.UserRole;
import com.example.demo.enums.UserTeam;
import com.example.demo.enums.UserType;
import com.example.demo.model.User;
import com.example.demo.repository.UserRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.annotation.Order;
import org.springframework.security.crypto.password.PasswordEncoder;

@Configuration
@RequiredArgsConstructor
@Order(1)
public class DataInitializer implements CommandLineRunner {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;

    @Override
    public void run(String... args) throws Exception {

        // Tạo admin nếu chưa tồn tại
        if (!userRepository.existsByEmail("admin@example.com")) {
            User admin = User.builder()
                    .name("Nguyễn Phúc Nhân")
                    .email("admin@example.com")
                    .password(passwordEncoder.encode("admin123"))
                    .role(UserRole.ROLE_ADMIN)
                    .team(UserTeam.RESEARCH)
                    .code("ADMIN001")
                    .type(UserType.DT)
                    .totalScore(10000)
                    .active(true)
                    .build();
            userRepository.save(admin);
        }

        // Tạo manager nếu chưa tồn tại
        if (!userRepository.existsByEmail("manager@example.com")) {
            User manager = User.builder()
                    .name("Trần Thị Lan")
                    .email("manager@example.com")
                    .password(passwordEncoder.encode("manager123"))
                    .role(UserRole.ROLE_MANAGER)
                    .team(UserTeam.ENGINEER)
                    .code("MANAGER001")
                    .type(UserType.DT)
                    .totalScore(5000)
                    .active(true)
                    .build();
            userRepository.save(manager);
        }

        // Tạo user nếu chưa tồn tại
        if (!userRepository.existsByEmail("user@example.com")) {
            User user = User.builder()
                    .name("Lê Văn Bình")
                    .email("user@example.com")
                    .password(passwordEncoder.encode("user123"))
                    .role(UserRole.ROLE_USER)
                    .team(UserTeam.MEDIA)
                    .code("USER001")
                    .type(UserType.DT)
                    .totalScore(1000)
                    .active(true)
                    .build();
            userRepository.save(user);
        }

        System.out.println("DataInitializer: Default users ensured");
    }
}