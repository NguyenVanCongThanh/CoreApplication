package com.example.demo.utils;

import java.security.SecureRandom;

public final class PasswordGenerator {

    private static final String UPPERCASE = "ABCDEFGHIJKLMNOPQRSTUVWXYZ";
    private static final String LOWERCASE = "abcdefghijklmnopqrstuvwxyz";
    private static final String DIGITS    = "0123456789";
    private static final String SPECIAL   = "!@#$%^&*()_+-=";
    private static final String ALL_CHARS = UPPERCASE + LOWERCASE + DIGITS + SPECIAL;
    private static final int    DEFAULT_LENGTH = 12;

    // ThreadLocal
    private static final ThreadLocal<SecureRandom> RANDOM =
            ThreadLocal.withInitial(SecureRandom::new);

    private PasswordGenerator() {}

    public static String generateStrongPassword() {
        return generateStrongPassword(DEFAULT_LENGTH);
    }

    public static String generateStrongPassword(int length) {
        if (length < 8) throw new IllegalArgumentException("Password length must be at least 8");

        var rng = RANDOM.get();
        var sb  = new StringBuilder(length);

        sb.append(UPPERCASE.charAt(rng.nextInt(UPPERCASE.length())));
        sb.append(LOWERCASE.charAt(rng.nextInt(LOWERCASE.length())));
        sb.append(DIGITS.charAt(rng.nextInt(DIGITS.length())));
        sb.append(SPECIAL.charAt(rng.nextInt(SPECIAL.length())));

        for (int i = 4; i < length; i++) {
            sb.append(ALL_CHARS.charAt(rng.nextInt(ALL_CHARS.length())));
        }

        return shuffle(sb.toString(), rng);
    }

    private static String shuffle(String s, SecureRandom rng) {
        char[] chars = s.toCharArray();
        for (int i = chars.length - 1; i > 0; i--) {
            int j    = rng.nextInt(i + 1);
            char tmp = chars[i];
            chars[i] = chars[j];
            chars[j] = tmp;
        }
        return new String(chars);
    }
}