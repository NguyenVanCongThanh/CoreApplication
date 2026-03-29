package com.example.demo.service.user;

import com.example.demo.dto.auth.PasswordChangeRequest;
import com.example.demo.dto.user.UpdateUserRequest;
import com.example.demo.dto.user.UserResponse;
import com.example.demo.model.User;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;

public interface UserService {

    List<UserResponse> getAllUsers();

    UserResponse getUserById(Long id);

    User getUserByEmail(String email);

    UserResponse updateUser(Long id, UpdateUserRequest request);

    UserResponse updateRole(Long id, com.example.demo.enums.UserRole role);

    void changePassword(Long userId, String currentPassword, String newPassword);

    void requestPasswordChange(PasswordChangeRequest request);

    void confirmPasswordChange(String token, String newPassword);

    String uploadProfilePicture(Long userId, MultipartFile file);

    void deleteUser(Long id);
}
