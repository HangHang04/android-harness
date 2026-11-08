---
name: android-harness
description: Control and inspect the user's authorized Android phone from Windows over wired or wireless ADB. Use for Android-only tasks that require diagnosing a connection, reading the current screen, taking screenshots, finding UI elements, tapping, swiping, pressing keys, opening apps, typing text, or running a verified multi-step phone workflow.
---

# Android Harness

Use `android-harness` as the thin control layer for one user-authorized Android 11+ device.

## Resolve the runtime

Prefer the bundled `scripts/invoke-android-harness.ps1`, resolved relative to this `SKILL.md`. It uses `android-harness.exe` when available and otherwise falls back to the installed Python module. Examples below use `android-harness` for brevity; substitute the invocation script when the command is not on `PATH`.

## Console tasks (preferred for ongoing control)

For visible progress, scoped grants and cancellation, use the local console and managed task API described in [references/managed-tasks.md](references/managed-tasks.md). Request only the device, applications and capabilities needed for the goal. Wait for the user to approve the request in the console. Execute subsequent actions through `task action`, then complete the task. Never approve your own request or fall back to legacy commands after a denied or revoked grant.

## Gate every session

1. Run `android-harness --json doctor` before the first phone action.
2. If the device is absent, unauthorized, offline, locked, or ambiguous, stop and relay the error.
3. Let the user pair wireless debugging, approve the RSA prompt, choose a device, and unlock the phone. Never perform or bypass those physical trust steps.

If USB or wireless discovery fails, read `references/wireless-debugging.md` before changing drivers, VPN, firewall, proxy, or phone settings.

Prefer a web, desktop, or API equivalent when it can complete the task without opening personal phone content.

## Observe, act, verify

- Read structured elements first with `android-harness --json ui`.
- Use `android-harness --json tap-text "Label"` for a unique label or content description.
- If labels are absent, run `android-harness screenshot`, view the returned image, then tap device-pixel coordinates with `android-harness --json tap X Y`.
- Use `swipe`, `scroll`, `key`, and `open-app` for navigation. `open-app` accepts a package name or a configured alias.
- Verify every meaningful action with `ui`, `screenshot`, or the `stable` result. Do not repeat a failed tap without re-reading the screen.
- Treat multiple text matches as ambiguous. Inspect the returned candidates and pass `--index` only after choosing the intended one.

Read text from stdin so it does not enter shell history:

```powershell
'hello' | android-harness --json type --stdin
```

Unicode text requires the optional companion IME. Installing or enabling it changes the phone and always requires the user's approval. The harness temporarily selects it for a commit and restores the previous keyboard.

For conditional or repeated workflows, write a local Python file and run:

```powershell
android-harness --serial DEVICE_SERIAL run .\workflow.py
```

The workflow receives `screen_info`, `screenshot`, `ui`, `find`, `tap`, `tap_text`, `long_press`, `swipe`, `scroll`, `press`, `type_text`, `open_app`, `wait_stable`, `scroll_until`, and `scroll_collect`.

## Consent and privacy

Within a console-approved task, ordinary actions covered by the stated goal and grant may continue without repeated questions. Obtain approval for additional outward-facing consequences outside that goal. Installation, deletion, permission changes and enabling an input method retain individual confirmation. A task grant cannot determine the business meaning of arbitrary buttons.

Read only the personal content necessary for the user's task. Do not browse adjacent messages, photos, mail, notifications, authentication codes, or account data. Never expose typed text or screenshots in logs unless the user explicitly requests artifacts.

## Failure boundaries

- One selected device per invocation; pass `--serial` when more than one is attached.
- Secure and DRM surfaces may return black screenshots or no UI nodes. Report the limitation; do not tap blindly.
- Vendor ROMs may require an additional USB debugging security toggle for input. Ask the user to change it themselves.
- ADB-only typing supports a restricted ASCII set. Never silently transliterate or drop unsupported characters.
- Android Harness does not support unlocking, authentication bypass, multi-touch, camera/biometric confirmation, or unattended connection recovery.
