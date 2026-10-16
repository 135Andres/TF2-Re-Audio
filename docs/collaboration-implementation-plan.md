# Collaboration Implementation Plan

> Execution: inline in this session, as authorized by the user's request to apply the accepted ideation.

**Goal:** Friends share recordings through a trusted optional host while preserving offline work and manual apply.
**Architecture:** Group event log and credentials; separate sync listener/client; existing local server orchestrates workers and tunnel; group panel uses local API only.
**Tech Stack:** Python >=3.10 standard library, plain JavaScript, unittest.
**Spec:** docs/collaboration-design.md

## Global constraints
Follow AGENTS.md, preserve existing work, atomic persistent writes, English UI, Windows/Linux paths, no real network/TF2 in tests.

## Review focus
- Existing solo history: explicit consent and backup; reject foreign unsignable history.
- Interrupted persistence: pending data remains retryable; rollback membership memory on failed writes.
- Forged forwarded records/admin events: reject unauthorized new records and immutable ID changes.
- Host changes: validate group identity and do not disclose bearer credentials through redirects.
- Closing/reconfiguration: stop workers/tunnel/listeners without deadlock or leaking into solo use.

## Task T11 — group.py / tests/test_group.py
- [x] Add failing tests for create/load, invitation single-use/expiry, role enforcement, removal propagation, token secrecy, snapshot mismatch, write failures and corruption.
- [x] Implement Group API from the spec, versioned events and atomic backups.
- [x] Run python -m unittest tests.test_group.

## Task T12 — sync.py / tests/test_sync.py
- [x] Add failing HTTP tests for auth, 426, 304 with outgoing data, malformed WAV/hash/path, foreign records/admin events, request limits and wrong group.
- [x] Implement SyncServer(store, group, port=0), sync_once(store, group, url, token), Syncer; expose SyncResult(pushed, pulled, conflicts, error).
- [x] Run python -m unittest tests.test_sync.

## Task T13 — tests/test_integration_sync.py
- [x] Add three-device tests for offline save, conflict convergence/resolution, stale original restore, host change, removal, interrupted retry and process restart.
- [x] Run integration tests; fix within the owning task before proceeding.

## Task T14 delivery 2 — server.py, __main__.py, tests/test_server.py, tests/test_cli.py
- [x] Add failing API tests for group creation/consent, invitation/join, grouped author identity, manual apply, lifecycle cleanup and wrong-group link.
- [x] Add local group endpoints, load/start/stop Syncer, separate SyncServer and optional Tunnel. CLI host opens local group controls.
- [x] Run API/CLI tests.

## Task T18 and T15 integration — web/group.js; index.html/app.js/strings.js and tests/test_web.py
- [x] Add group controls/status/consent, invitation sharing, roles, suggested voice and hosting. Keep strings centralized and safe textContent rendering.
- [x] Verify browser create/invite flow with fixtures, keyboard dialog exit, and absence of automatic apply.

## Verification and report
- [x] Run python -m unittest with Chromium; run git diff --check. Final results are recorded in docs/collaboration-report.md.
- [x] Review authorization, staged audio ordering, persistence recovery and shutdown.
- [x] Record remaining real-network/Windows/TF2 checks and owner requests in docs/collaboration-report.md.

## Implementation rulings
- No T8 source edits: validated audio is staged by sync before metadata commit; GroupStore supplies a conservative no-prune shared-history policy through existing hooks. Public storage APIs are an owner handoff.
- Initial data transfer uses HTTPS bearer credentials; only hashes enter replicated membership state. Do not interpret older plan wording as transmitting only a hash in the Authorization header.
- Offline host takeover is allowed with the saved replica and a visible completeness warning.
- Historical solo tombstones are not evidence permitting deletion on another device.
- Final independent review found retention/forged-tombstone issues; targeted regression tests reproduced them before fixes. A second review confirmed the fixes and identified pending accounting, also reproduced and fixed.
- No publication, real tunnel launch, native Windows validation or TF2 acceptance was performed.
