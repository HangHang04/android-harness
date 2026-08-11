# Android Harness

Android Harness lets an agent inspect and control one real Android phone from a Windows computer through ADB. It keeps the same thin, editable shape as [phone-harness](https://github.com/ShawnPana/phone-harness), but uses Android's native screenshot, UI Automator, and input facilities instead of a desktop mirroring window.

The host runtime does not require root, scrcpy, Appium, or a permanently running phone service.

## What it can do

- Diagnose ADB, authorization, Android version, lock state, screenshots, and UI access.
- Capture the current screen as a PNG.
- Read visible text, content descriptions, resource IDs, bounds, and interaction flags.
- Tap by coordinates or unique visible text.
- Long-press, swipe, scroll, press system keys, and open apps by package name.
- Wait for a screen to become stable and detect whether a scroll actually moved.
- Run explicit Python workflow files with pre-imported helpers.
- Optionally type Chinese, emoji, and arbitrary Unicode through a small companion IME.
- Print a compact Codex/Claude skill with `android-harness skill`.

## Requirements

- Windows 10 or 11.
- Python 3.11 or newer.
- Android SDK Platform Tools (`adb.exe`).
- A real Android device on Android 11 / API 30 or newer with USB or wireless debugging enabled.

Read [install.md](install.md) for the pairing, authorization, and optional companion steps.

## Quick start

Run these commands from the project root in PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\android-harness.exe --json doctor
```

To run the working tree immediately without installing build dependencies:

```powershell
.\android-harness.ps1 --json doctor
```

Basic operations:

```powershell
android-harness --json screen-info
android-harness screenshot
android-harness --json ui
android-harness --json tap-text 'Settings'
android-harness --json swipe up
android-harness --json key home
android-harness --json open-app com.android.settings
'hello from Android Harness' | android-harness --json type --stdin
```

Global options such as `--serial`, `--adb`, and `--json` must appear before the subcommand.

When more than one device is attached, select one explicitly:

```powershell
android-harness --serial 'DEVICE_SERIAL' --json doctor
```

## Python workflows

Create a workflow file:

```python
print(screen_info())
open_app("com.android.settings")
tap_text("Network & internet")
print([row["text"] for row in ui() if row["text"]])
```

Then run it:

```powershell
android-harness run .\workflow.py
```

The helpers available to workflows are documented by:

```powershell
android-harness skill
```

Project-local helpers placed in `agent-workspace\agent_helpers.py` are loaded only by the explicit workflow runner. The included file is intentionally empty so task-specific helpers stay reviewable.

## Configuration

Android Harness reads `%APPDATA%\android-harness\config.json` by default. Copy [config.example.json](config.example.json) and adjust it if you want a default device or friendly app aliases:

```json
{
  "default_serial": "DEVICE_SERIAL",
  "command_timeout": 15,
  "app_aliases": {
    "settings": "com.android.settings"
  }
}
```

Environment overrides:

- `ANDROID_HARNESS_ADB`: exact path to `adb.exe`.
- `ANDROID_HARNESS_SERIAL`: default device serial.
- `ANDROID_HARNESS_CONFIG`: alternate config file.
- `ANDROID_HARNESS_AGENT_HELPERS`: alternate project helper file.

## Safety model

Connection trust stays with the user. Android Harness never approves RSA authorization, unlocks a phone, bypasses authentication, or silently selects among multiple devices. Installing or enabling the optional companion requires an explicit `--confirm` flag after the user agrees.

The bundled Skill requires confirmation before messages, purchases, deletion, posting, settings or permission changes, and other outward-facing or hard-to-reverse actions. Screenshots use a stable file under the Windows temporary directory and are overwritten on the next capture for the same device; no activity log is written by default.

## Development

The host package has no third-party runtime dependencies. Run the standard-library tests without installing development extras:

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
py -3 -m unittest discover -s tests -v
```

If the optional development tools are installed:

```powershell
py -3 -m pytest
py -3 -m ruff check .
```

The optional IME lives in `companion\` and has a separate Gradle/JDK toolchain.

## Limits

- UI Automator only exposes accessible nodes. Canvas, games, and unlabeled icons need screenshot-based visual reasoning.
- Secure and DRM surfaces may render black and may expose no nodes.
- ADB-only typing intentionally accepts a restricted ASCII set; Unicode needs the optional companion.
- No multi-touch, biometric/camera confirmation, remote unlocking, device farm, or unattended reconnect flow.

## Acknowledgements / 致谢

Android Harness was inspired by [ShawnPana/phone-harness](https://github.com/ShawnPana/phone-harness), especially its thin, agent-oriented “observe, act, verify” workflow. This repository is an independent Android/ADB implementation. Thanks to ShawnPana for sharing the original project and its ideas publicly.
