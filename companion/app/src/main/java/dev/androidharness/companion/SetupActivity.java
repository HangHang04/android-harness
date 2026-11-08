package dev.androidharness.companion;

import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.os.Bundle;
import android.provider.Settings;
import android.text.InputType;
import android.view.ViewGroup;
import android.view.inputmethod.InputMethodManager;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

public final class SetupActivity extends Activity {
    private TextView status;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setTitle(R.string.app_name);

        int padding = Math.round(24 * getResources().getDisplayMetrics().density);
        LinearLayout content = new LinearLayout(this);
        content.setBackgroundColor(0xFFF7FAFF);
        content.setOrientation(LinearLayout.VERTICAL);
        content.setPadding(padding, padding, padding, padding);

        TextView title = new TextView(this);
        title.setText(R.string.setup_title);
        title.setTextSize(28);
        title.setTextColor(0xFF24374E);
        content.addView(title, matchWidthWrapHeight());

        TextView explanation = new TextView(this);
        explanation.setText(R.string.setup_body);
        explanation.setTextSize(16);
        content.addView(explanation, matchWidthWrapHeight());

        status = new TextView(this);
        status.setTextSize(16);
        content.addView(status, matchWidthWrapHeight());

        Button settingsButton = new Button(this);
        settingsButton.setText(R.string.open_keyboard_settings);
        settingsButton.setOnClickListener(
                view -> startActivity(new Intent(Settings.ACTION_INPUT_METHOD_SETTINGS)));
        content.addView(settingsButton, matchWidthWrapHeight());

        Button pickerButton = new Button(this);
        pickerButton.setText(R.string.show_keyboard_picker);
        pickerButton.setOnClickListener(view -> {
            InputMethodManager manager =
                    (InputMethodManager) getSystemService(Context.INPUT_METHOD_SERVICE);
            manager.showInputMethodPicker();
        });
        content.addView(pickerButton, matchWidthWrapHeight());

        EditText testField = new EditText(this);
        testField.setHint(R.string.test_field_hint);
        testField.setInputType(InputType.TYPE_CLASS_TEXT | InputType.TYPE_TEXT_FLAG_MULTI_LINE);
        testField.setMinLines(4);
        content.addView(testField, matchWidthWrapHeight());

        ScrollView scrollView = new ScrollView(this);
        scrollView.addView(content);
        scrollView.setFillViewport(true);
        scrollView.setOnApplyWindowInsetsListener((view, insets) -> {
            android.graphics.Insets bars = insets.getInsets(
                    android.view.WindowInsets.Type.systemBars()
                    | android.view.WindowInsets.Type.ime());
            view.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return insets;
        });
        setContentView(scrollView);
    }

    @Override
    protected void onResume() {
        super.onResume();
        String enabled = Settings.Secure.getString(
                getContentResolver(), Settings.Secure.ENABLED_INPUT_METHODS);
        boolean isEnabled = enabled != null && enabled.contains(getPackageName());
        String current = Settings.Secure.getString(
                getContentResolver(), Settings.Secure.DEFAULT_INPUT_METHOD);
        status.setText(getString(R.string.status_summary,
                getString(isEnabled ? R.string.status_enabled : R.string.status_disabled),
                getString(R.string.current_keyboard, current == null ? "—" : current)));
    }

    private static LinearLayout.LayoutParams matchWidthWrapHeight() {
        LinearLayout.LayoutParams params = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT);
        params.bottomMargin = 24;
        return params;
    }
}
