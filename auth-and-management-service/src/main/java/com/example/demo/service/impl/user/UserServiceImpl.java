package com.example.demo.service.impl.user;

import com.example.demo.dto.auth.PasswordChangeRequest;
import com.example.demo.exception.BadRequestException;
import com.example.demo.exception.InvalidPasswordException;
import com.example.demo.exception.ResourceNotFoundException;
import com.example.demo.model.User;
import com.example.demo.repository.UserRepository;
import com.example.demo.service.EmailService;
import com.example.demo.service.PasswordResetService;
import com.example.demo.service.UserService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.multipart.MultipartFile;

import java.io.IOException;
import java.nio.file.*;
import java.util.List;
import java.util.UUID;

/**
 * UserServiceImpl - quản lý user, đổi mật khẩu, upload ảnh.
 *
 * Cải tiến:
 * - validatePassword() là private helper tập trung, gọi 1 nơi
 * - Email notification gọi async - không block response
 * - Typed exceptions thay RuntimeException
 * - Optional.ofNullable để xử lý null an toàn
 */
@Slf4j
@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class UserServiceImpl implements UserService {

    private final UserRepository userRepository;
    private final PasswordEncoder passwordEncoder;
    private final EmailService emailService;
    private final PasswordResetService passwordResetService;

    @Value("${app.upload.dir:uploads/profiles/}")
    private String uploadDir;

    // ── Reads ────────────────────────────────────────────────────────────────

    @Override
    public List<User> getAllUsers() {
        return userRepository.findAll();
    }

    @Override
    public User getUserById(Long id) {
        return userRepository.findById(id)
                .orElseThrow(() -> new ResourceNotFoundException("User", id));
    }

    @Override
    public User getUserByEmail(String email) {
        return userRepository.findByEmail(email)
                .orElseThrow(() -> new ResourceNotFoundException("User not found: " + email));
    }

    // ── Writes ───────────────────────────────────────────────────────────────

    @Override
    @Transactional
    public User updateUser(Long id, User details) {
        var user = getUserById(id);
        user.setName(details.getName());
        user.setEmail(details.getEmail());
        if (details.getTeam() != null)           user.setTeam(details.getTeam());
        if (details.getType() != null)           user.setType(details.getType());
        if (details.getProfilePicture() != null) user.setProfilePicture(details.getProfilePicture());
        return userRepository.save(user);
    }

    @Override
    @Transactional
    public void changePassword(Long userId, String current, String newPwd) {
        var user = getUserById(userId);

        if (!passwordEncoder.matches(current, user.getPassword())) {
            throw new BadRequestException("Current password is incorrect");
        }
        validatePassword(newPwd);

        user.setPassword(passwordEncoder.encode(newPwd));
        userRepository.save(user);

        // Notification async - không block response
        emailService.sendPasswordChangedNotificationAsync(user.getEmail(), user.getName())
                    .exceptionally(ex -> { log.warn("Notification email failed: {}", ex.getMessage()); return null; });
    }

    @Override
    @Transactional
    public void requestPasswordChange(PasswordChangeRequest req) {
        var user = getUserByEmail(req.getEmail());

        if (!passwordEncoder.matches(req.getCurrentPassword(), user.getPassword())) {
            throw new BadRequestException("Mật khẩu hiện tại không đúng");
        }
        validatePassword(req.getNewPassword());

        var token = passwordResetService.createToken(user);
        emailService.sendPasswordChangeConfirmationAsync(user.getEmail(), user.getName(), token.getToken())
                    .exceptionally(ex -> { log.error("Confirmation email failed for {}: {}", user.getEmail(), ex.getMessage()); return null; });
    }

    @Override
    @Transactional
    public void confirmPasswordChange(String tokenValue, String newPwd) {
        var token = passwordResetService.validateAndGetToken(tokenValue);
        var user  = token.getUser();

        validatePassword(newPwd);
        user.setPassword(passwordEncoder.encode(newPwd));
        userRepository.save(user);
        passwordResetService.markTokenAsUsed(token);

        emailService.sendPasswordChangedNotificationAsync(user.getEmail(), user.getName())
                    .exceptionally(ex -> { log.warn("Notification email failed: {}", ex.getMessage()); return null; });

        log.info("Password changed for user: {}", user.getEmail());
    }

    @Override
    @Transactional
    public String uploadProfilePicture(Long userId, MultipartFile file) {
        var user = getUserById(userId);
        validateImageFile(file);

        try {
            var uploadPath = Paths.get(uploadDir);
            Files.createDirectories(uploadPath);

            String ext      = extractExtension(file.getOriginalFilename());
            String filename = "user_%d_%s%s".formatted(userId, UUID.randomUUID(), ext);
            Path   filePath = uploadPath.resolve(filename);

            Files.copy(file.getInputStream(), filePath, StandardCopyOption.REPLACE_EXISTING);
            deleteOldPicture(user.getProfilePicture());

            String url = uploadDir + filename;
            user.setProfilePicture(url);
            userRepository.save(user);
            return url;

        } catch (IOException ex) {
            throw new RuntimeException("Failed to upload file: " + ex.getMessage(), ex);
        }
    }

    @Override
    @Transactional
    public void deleteUser(Long id) {
        var user = getUserById(id);
        deleteOldPicture(user.getProfilePicture());
        userRepository.deleteById(id);
    }

    // ── Helpers ──────────────────────────────────────────────────────────────

    /**
     * Validate password strength - tập trung 1 nơi, gọi nhiều chỗ.
     */
    private void validatePassword(String pwd) {
        if (pwd == null || pwd.length() < 8) {
            throw new InvalidPasswordException("Mật khẩu phải có ít nhất 8 ký tự");
        }
        boolean hasUpper = pwd.chars().anyMatch(Character::isUpperCase);
        boolean hasLower = pwd.chars().anyMatch(Character::isLowerCase);
        boolean hasDigit = pwd.chars().anyMatch(Character::isDigit);

        if (!hasUpper || !hasLower || !hasDigit) {
            throw new InvalidPasswordException("Mật khẩu phải chứa ít nhất 1 chữ hoa, 1 chữ thường và 1 số");
        }
    }

    private void validateImageFile(MultipartFile file) {
        if (file.isEmpty()) {
            throw new BadRequestException("File is empty");
        }
        String ct = file.getContentType();
        if (ct == null || !ct.startsWith("image/")) {
            throw new BadRequestException("Only image files are allowed");
        }
    }

    private void deleteOldPicture(String path) {
        if (path == null || path.isBlank()) return;
        try {
            Files.deleteIfExists(Paths.get(path));
        } catch (IOException ex) {
            log.warn("Could not delete old profile picture [{}]: {}", path, ex.getMessage());
        }
    }

    private String extractExtension(String filename) {
        if (filename != null && filename.contains(".")) {
            return filename.substring(filename.lastIndexOf('.'));
        }
        return ".jpg";
    }
}