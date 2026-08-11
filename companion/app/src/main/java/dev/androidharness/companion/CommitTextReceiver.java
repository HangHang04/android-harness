package dev.androidharness.companion;

import android.app.Activity;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public final class CommitTextReceiver extends BroadcastReceiver {
    static final String ACTION_COMMIT_TEXT = "dev.androidharness.action.COMMIT_TEXT";
    static final String EXTRA_TEXT_BASE64 = "text_b64";

    @Override
    public void onReceive(Context context, Intent intent) {
        if (!ACTION_COMMIT_TEXT.equals(intent.getAction())) {
            fail("unexpected-action");
            return;
        }
        String encoded = intent.getStringExtra(EXTRA_TEXT_BASE64);
        if (encoded == null) {
            fail("missing-text");
            return;
        }

        final String text;
        try {
            text = TextPayload.decode(encoded);
        } catch (IllegalArgumentException error) {
            fail("invalid-base64");
            return;
        }

        HarnessImeService service = HarnessImeService.current();
        if (service == null) {
            fail("ime-not-active");
            return;
        }
        if (!service.commitText(text)) {
            fail("no-input-connection");
            return;
        }
        setResultCode(Activity.RESULT_OK);
        setResultData("ok");
    }

    private void fail(String reason) {
        setResultCode(Activity.RESULT_CANCELED);
        setResultData(reason);
    }
}
