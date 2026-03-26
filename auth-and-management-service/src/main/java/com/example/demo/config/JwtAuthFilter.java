package com.example.demo.config;

import com.example.demo.service.JwtService;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.WebAuthenticationDetailsSource;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.filter.OncePerRequestFilter;

import java.io.IOException;
import java.util.Arrays;
import java.util.List;
import java.util.Optional;

@Slf4j
@Component
@RequiredArgsConstructor
public class JwtAuthFilter extends OncePerRequestFilter {

    private static final String BEARER_PREFIX   = "Bearer ";
    private static final String AUTH_COOKIE_NAME = "authToken";

    private final JwtService jwtService;

    @Override
    protected void doFilterInternal(HttpServletRequest req,
                                    HttpServletResponse res,
                                    FilterChain chain) throws ServletException, IOException {

        extractToken(req).ifPresent(token -> authenticate(token, req));

        chain.doFilter(req, res);
    }

    private Optional<String> extractToken(HttpServletRequest req) {
        String header = req.getHeader("Authorization");
        if (StringUtils.hasText(header) && header.startsWith(BEARER_PREFIX)) {
            return Optional.of(header.substring(BEARER_PREFIX.length()));
        }

        if (req.getCookies() != null) {
            return Arrays.stream(req.getCookies())
                    .filter(c -> AUTH_COOKIE_NAME.equals(c.getName()))
                    .map(Cookie::getValue)
                    .filter(StringUtils::hasText)
                    .findFirst();
        }

        return Optional.empty();
    }

    private void authenticate(String token, HttpServletRequest req) {
        if (SecurityContextHolder.getContext().getAuthentication() != null) return;

        if (!jwtService.validateToken(token)) {
            log.debug("JWT validation failed for request: {}", req.getRequestURI());
            return;
        }

        try {
            String email         = jwtService.extractEmail(token);
            List<String> roles   = jwtService.extractRoles(token);
            var authorities      = buildAuthorities(roles);

            var auth = new UsernamePasswordAuthenticationToken(email, null, authorities);
            auth.setDetails(new WebAuthenticationDetailsSource().buildDetails(req));
            SecurityContextHolder.getContext().setAuthentication(auth);

            log.debug("Authenticated [{}] with roles {}", email, roles);
        } catch (Exception ex) {
            log.warn("Could not set authentication from JWT: {}", ex.getMessage());
        }
    }


    private List<SimpleGrantedAuthority> buildAuthorities(List<String> roles) {
        if (roles == null || roles.isEmpty()) {
            return List.of(new SimpleGrantedAuthority("ROLE_STUDENT"));
        }
        return roles.stream()
                .map(r -> new SimpleGrantedAuthority(r.startsWith("ROLE_") ? r : "ROLE_" + r))
                .toList();
    }
}