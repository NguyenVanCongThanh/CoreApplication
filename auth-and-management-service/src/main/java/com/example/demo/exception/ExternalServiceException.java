package com.example.demo.exception;


import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ResponseStatus;

@ResponseStatus(HttpStatus.INTERNAL_SERVER_ERROR)
public class ExternalServiceException extends AppException {
    public ExternalServiceException(String service, String reason) {
        super("External service [" + service + "] failed: " + reason);
    }
    public ExternalServiceException(String service, String reason, Throwable cause) {
        super("External service [" + service + "] failed: " + reason, cause);
    }
}
