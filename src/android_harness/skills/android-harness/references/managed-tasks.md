# Console-managed tasks

Start `android-harness console` on the computer. The browser is the user's approval surface.
Use stdin JSON for payloads, never shell-interpolate task text or secrets.

1. Discover devices with `devices`; request a task with `task request --stdin`:
   `{"goal":"Inspect Android settings","serial":"DEVICE","packages":["com.android.settings"],"capabilities":["observe","interact"]}`.
2. Tell the user what was requested and wait for approval. `task list` reports pending/active state.
3. Use `task action ID open-app --stdin` with `{"package":"com.android.settings"}`.
4. Use `task action ID observe --stdin` with `{"screenshot":false}`. Screenshot opt-in returns `image_base64` for direct display, not persistent logging.
5. `task action ID tap-element --stdin` accepts `{"selector":{"resource_id":"android:id/title","text":"Exact label"}}`. Multiple candidates are an error; refine the selector.
6. `task action ID wait-for --stdin` accepts `{"selector":{"text":"Label"},"timeout":6,"absent":false}`.
7. `task action ID batch --stdin` accepts `{"steps":[{"action":"key","args":{"key":"back"},"after":{"selector":{"text":"Settings"},"timeout":6}}]}`. Each step can have `before`/`after` wait conditions. A failure stops the task; do not automatically retry mutations.
8. Finish with `task complete ID`, or stop with `task stop ID`.

Capabilities are `observe`, `interact`, `files`. A task lasts at most 30 minutes, binds one device and explicit package names, and is invalid after console restart. Home/back can leave the permitted application: the task then stops. Grant the launcher's actual package only when necessary for the goal. Opening an explicitly allowed app is permitted from outside its screen; other operations require the foreground app to be in scope.

`task action ID capabilities` reports available features. `open-url` accepts only HTTP/HTTPS URLs and an explicit authorized `package`.

For file transfer request `files` and explicit existing `local_root` and `remote_root` (under `/sdcard`). Use `files push --task ID --stdin` or `files pull --task ID --stdin`, payload `{"local":"E:/files/example.txt","remote":"/sdcard/Download/AndroidHarness/example.txt"}`. Parents must exist; directories and overwrite are not accepted.

The task API does not accept arbitrary ADB, shell or Python commands. Legacy CLI commands and `run` are trusted local tools, outside managed grants. Do not use them to bypass a revoked or denied task. App checks are tool policy, not OS isolation; arbitrary tap semantics cannot identify every payment, message or deletion. Obtain explicit approval for consequences outside the requested goal, and individually confirm installation, deletion and permission changes.
