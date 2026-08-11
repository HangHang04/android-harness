package dev.androidharness.companion;

import android.inputmethodservice.InputMethodService;
import android.view.inputmethod.InputConnection;

import java.lang.ref.WeakReference;

public final class HarnessImeService extends InputMethodService {
    private static WeakReference<HarnessImeService> active = new WeakReference<>(null);

    @Override
    public void onCreate() {
        super.onCreate();
        active = new WeakReference<>(this);
    }

    @Override
    public void onDestroy() {
        HarnessImeService current = active.get();
        if (current == this) {
            active.clear();
        }
        super.onDestroy();
    }

    static HarnessImeService current() {
        return active.get();
    }

    boolean commitText(String text) {
        InputConnection connection = getCurrentInputConnection();
        return connection != null && connection.commitText(text, 1);
    }
}
