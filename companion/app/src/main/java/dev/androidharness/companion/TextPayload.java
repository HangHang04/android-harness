package dev.androidharness.companion;

import java.nio.charset.StandardCharsets;
import java.util.Base64;

final class TextPayload {
    private TextPayload() {
    }

    static String decode(String encoded) {
        byte[] bytes = Base64.getUrlDecoder().decode(encoded);
        return new String(bytes, StandardCharsets.UTF_8);
    }
}
