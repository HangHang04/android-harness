# Android Harness installation

Use these steps once. Normal phone tasks should follow the bundled `SKILL.md` printed by `android-harness skill`.

## 1. Host setup

Requirements:

- PowerShell 7 is recommended.
- Python 3.11+.
- Android SDK Platform Tools.

From the repository root:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\android-harness.exe devices
```

ADB is resolved in this order:

1. `ANDROID_HARNESS_ADB`.
2. `adb.exe` on `PATH`.
3. `ANDROID_SDK_ROOT` or `ANDROID_HOME`.
4. `%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe`.

## 2. Connect a phone

On the phone, enable Developer options and USB debugging. Connect the cable, unlock the phone, and approve the RSA fingerprint shown by Android. These trust steps must be completed by the user.

Verify:

```powershell
android-harness devices
android-harness --json doctor
```

For Android 11+, wireless debugging can be paired after the initial setup:

```powershell
adb pair 'PHONE_IP:PAIRING_PORT'
adb connect 'PHONE_IP:DEBUG_PORT'
android-harness devices
```

Enter the pairing code shown by the phone. The pairing and debugging ports can differ. VPNs, guest Wi-Fi, client isolation, or blocked mDNS can prevent discovery; use USB when diagnosing those cases.

Some vendor ROMs, especially some Xiaomi-family devices, require a separate **USB debugging (Security settings)** toggle before injected taps work. Let the user change that setting and restart the phone if the ROM asks for it.

## 3. Register the Agent Skill

For Codex:

```powershell
$skillDir = Join-Path $env:USERPROFILE '.codex\skills\android-harness'
New-Item -ItemType Directory -Path $skillDir -Force | Out-Null
android-harness skill | Set-Content -LiteralPath (Join-Path $skillDir 'SKILL.md') -Encoding utf8
```

For Claude Code, use `%USERPROFILE%\.claude\skills\android-harness\SKILL.md` instead. Re-run the command after updating Android Harness so the registered copy stays current.

## 4. Optional Unicode companion

The core harness works without an APK. Build the companion only when reliable Chinese, emoji, or other Unicode input is needed.

Build requirements:

- JDK 17.
- Android SDK Platform 35 and Build Tools 35.

Build from PowerShell:

```powershell
Set-Location -LiteralPath .\companion
.\gradlew.bat :app:assembleDebug
```

After reviewing the APK and getting the user's approval:

```powershell
android-harness helper install '.\companion\app\build\outputs\apk\debug\app-debug.apk' --confirm
android-harness helper enable --confirm
android-harness helper status
```

Enabling registers the keyboard but does not leave it selected. During Unicode input the harness saves the current keyboard, briefly selects the companion, commits the text, and restores the previous keyboard in a `finally` path.

If an OEM rejects the bridge permission or the helper cannot see a focused text field, the command fails without falling back to lossy input.

## 5. Troubleshooting ladder

Fix the first required failure from `android-harness --json doctor`:

1. ADB executable missing.
2. No attached device or multiple devices without `--serial`.
3. Device unauthorized or offline.
4. Android version below API 30.
5. Device locked.
6. Screenshot unavailable or black secure surface.
7. UI hierarchy empty or malformed.

The optional Unicode companion appears as a non-required doctor check.
