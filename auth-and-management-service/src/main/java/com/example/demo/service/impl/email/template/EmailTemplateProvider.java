package com.example.demo.service.impl.email.template;

public interface EmailTemplateProvider {
    String buildWelcomeHtml(String name, String email, String password);
    String buildPasswordConfirmHtml(String name, String token);
    String buildPasswordChangedHtml(String name);
}