# Friend invitation UX report — 2026-10-16

## Delivered

The approved bounded flow is implemented in T18 group.js, integrated through T15 index.html, strings.js, app.js and browser acceptance tests. Group offers separate Invite friends / Join friends paths. Creating a group leads to Start sharing and Share invite. Members, roles, cast and host address changes live in an advanced disclosure.

The generated invitation contains a link to http://127.0.0.1:8440/#join?host=<encoded-host>, a separate single-use code, and fallback instructions. It deliberately uses the recipient's default local port rather than the sender's potentially different port. Opening the link fills the host, removes the fragment from the address bar and requires confirmation. Pasting the complete message fills the host and code; legacy host-plus-code messages are also accepted. Existing membership is preserved. The UI rejects malformed invitation destinations and never joins automatically. Backend destination policy/security hardening is a separate scope.

Both people must install and open the same app build. If the app is closed or uses a different local port, the link cannot open it; paste the message in the running app instead. An invitation is enabled while hosting or synced with a host; that observed status cannot guarantee future availability. Stale displayed invitations are cleared when the known host changes or sync becomes unavailable. Updated docs/group-sharing.md describes the controls and limitations.

## Verification

- Before implementation, new Chromium checks failed because Join friends and direct invitation opening were missing.
- Targeted Chromium checks passed for creation, disabled invitations before hosting, generated link/code separation, complete-message fallback, malformed links, keyboard Escape/focus return, actual fixture join/download and manual Apply. An invalid code can be corrected while retaining the connection.
- Full integrated checkout: `python -m unittest` with TF2RA_PLAYWRIGHT and TF2RA_BROWSER set to installed local Playwright/Chromium: **244 tests, OK, 2 skipped** (97.929 seconds). All servers and TF2 data were temporary fixtures; no real game or public tunnel used.
- A mobile viewport screenshot at 390 × 844 was inspected: /tmp/tf2ra-invite-mobile.png. The modal scrolls and its controls fit the viewport.
- git diff --check passed.

The run emitted the existing duplicate-ZIP fixture warning and a local server BrokenPipeError when a browser connection closed. The suite passed, but server disconnect handling remains an owner request rather than a claim of clean server output.

## Not tested / owner requests

- Native Windows, physical microphone, real TF2/Casual, actual Cloudflare hosting, two physical PCs, Firefox, screen readers and complete accessibility acceptance: not run.
- T14 server.py: handle disconnected static/error response writes without printing a BrokenPipeError traceback. No server.py changes made here.
- T19 packaging: rebuild and identify a candidate containing this UI before sharing it with Windows testers. Existing ZIPs were not regenerated.
- T11/T12 protocol: no changes requested for this UX; existing invitation expiry/single-use semantics remain. Public hosting security acceptance remains governed by docs/security-next-steps.md.
- Concurrent edits to sync.py, tests/test_sync.py and docs/security-next-steps.md were present and were left untouched. The full suite result reflects the integrated checkout, not those changes authored by this task.
