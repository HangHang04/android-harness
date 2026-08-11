package dev.androidharness.companion;

import static org.junit.Assert.assertEquals;

import org.junit.Test;

import java.nio.charset.StandardCharsets;
import java.util.Base64;

public final class TextPayloadTest {
    @Test
    public void decodesUnicodeUrlSafeBase64() {
        String expected = "你好 👋\nAndroid Harness";
        String encoded = Base64.getUrlEncoder().encodeToString(
                expected.getBytes(StandardCharsets.UTF_8));

        assertEquals(expected, TextPayload.decode(encoded));
    }

    @Test(expected = IllegalArgumentException.class)
    public void rejectsInvalidBase64() {
        TextPayload.decode("not valid base64!");
    }
}
