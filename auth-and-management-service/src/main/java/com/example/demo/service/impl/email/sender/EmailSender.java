package com.example.demo.service.impl.email.sender;

public interface EmailSender {
    void send(String to, String subject, String content);
}
