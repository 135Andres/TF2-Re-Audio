# Tester Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task if separately assigned implementation. This document does not authorize execution. The user explicitly requested planning only; do not implement, delegate, commit product changes, or publish a release in this planning session.

**Goal:** Give Windows and Linux testers one shareable diagnostic ZIP that explains the last attempted action, its result and the next useful check, without exposing recordings or credentials.

**Architecture:** Extend the existing `doctor`, local HTTP API and settings flows. A small shared diagnostics module records structured events through atomic writes and produces an allowlisted support bundle. Browser failures use a protected local endpoint; manual test outcomes remain distinct from automatic observations.

**Tech Stack:** Python >=3.10, standard library only; existing vanilla JavaScript; unittest; existing optional Chromium harness; native Windows acceptance.

**Spec:** The design contract below, derived from the user's request for shareable Windows testing logs and the proposed scope in this conversation. Read `PLAN.md`, `TASKS.md`, `AGENTS.md` and this document before execution.

**Status:** Plan only. Baseline inspected: `9fdd526e40a9d5be51537363b348e9f08b1e689e`, the published v0.1.0 preview. No diagnostics implementation currently exists. Historical reports in PLAN/TASKS do not override current user instructions.

## Global constraints

- Python >=3.10, standard library only. No `pip install`.
- Windows and Linux; paths use pathlib; text explicitly uses UTF-8 and LF when serialized.
- All persistent application-data writes use `util.atomic_write`; do not use the standard logging FileHandler/RotatingFileHandler to append directly.
- Tests use unittest, temporary fixtures and loopback servers on `127.0.0.1` with port 0; no real TF2 or external network.
- Product text is English. Expected failures show clear messages, never a user-facing traceback.
- Preserve TASKS.md ownership. Each work item below is a handoff to the listed existing owner, not permission to edit another owner's files. Register ownership for new files before implementing them.
- No automatic upload, external telemetry, arbitrary filesystem collection, audio collection or changes to game/network behavior.
- Logging failure must never cause a recording, save, apply or normal shutdown to fail.

## Review focus

1. Disk full, denied writes or Windows file locks: preserve primary operation and show diagnostics degradation; test in D1/D2.
2. Secrets embedded in exception messages, URL fragments or browser events: reject unstructured content before persistence, not just before export; test in D1/D3/D4.
3. Export during concurrent logging/rotation: valid bounded ZIP with complete JSON lines and explicit omissions; test in D1/D2.
4. Browser cannot contact the server: report retrieval needs a CLI fallback and browser failures must not recursively log themselves; test in D3/D4.
5. Python is unavailable or its download fails: app logs cannot exist yet; expose a copyable launcher stage code without claiming automatic coverage; test in D6.

## Design contract

### Tester workflow and evidence

1. Launch the app normally; diagnostic recording starts automatically once Python enters the app.
2. Reproduce the problem once.
3. In **Setup & settings → Diagnostics**, select the tested step and an optional structured outcome, then choose **Download diagnostic report**.
4. Share `TF2ReAudio-diagnostics-<UTC timestamp>-<random suffix>.zip` manually with the maintainer.
5. If the UI will not open but Python works, run `TF2ReAudio.cmd doctor --bundle` or `sh tf2reaudio.sh doctor --bundle`. The command prints the bundle's local path even when TF2 is missing.
6. If Python cannot start, copy the launcher's short failure code and last visible step using the documented fallback. Do not tell the tester to run a Python command when Python is unavailable.

The report answers: app/build version, OS/Python/browser family and version, available browser capabilities, last operation, stable failure code, exception class, numeric errno/winerror, sanitized stack locations for unexpected Python faults, and the next suggested action.

Use outcomes `ok`, `failed`, `unsupported`, `not_tested`, `blocked`; manual outcomes also carry `source: tester`. An unobserved step is `not_tested`. Only classify `unsupported` when capability detection establishes it; denied permission is a failure, not missing browser support. Sending `snd_restart` does not establish that the replacement was heard. Playback, Casual interruption and real sharing require tester confirmation.

Manual checklist steps: `launch`, `tf2_detection`, `microphone`, `record`, `preview`, `save`, `apply`, `heard_in_tf2`, `restore`, `backup_restore`, `sharing`. Choose a fixed reason such as `permission_denied`, `device_missing`, `game_closed`, `write_denied`, `feature_unavailable`, `other`; no free-form notes are persisted in v1. Testers send their own reproduction steps alongside the ZIP. Logs cannot automatically establish missing product requirements.

### Storage, privacy and bounds

- Store under `data_dir()/logs`: Windows `%APPDATA%/TF2ReAudio/logs`; Linux `$XDG_DATA_HOME/tf2reaudio/logs` or its existing fallback.
- Four log files total: `events.jsonl` plus `.1`, `.2`, `.3`; each <=262144 bytes. Rotate before exceeding the cap. Keep a sanitized in-memory ring of the last 100 events when persistence is unavailable.
- Each event is one UTF-8 JSON line, <=4096 bytes, with schema version 1, UTC timestamp, random per-process session ID, sequence number, component, action, outcome, stable code and an allowlisted details object. Operation ID connects start/result events. Session IDs do not reuse account/device/member IDs.
- Details allow only validated enums, booleans, bounded counts/durations, exception type, errno/winerror and at most 20 stack frames containing application-relative module names, function names and line numbers. No traceback source text, locals or raw exception strings.
- Never persist HTTP bodies/headers, query strings/fragments, URLs, absolute paths, usernames, device labels/IDs, host/IP addresses, group/display names, passwords, invitation codes, auth tokens or recording content. Drop unknown fields. Test hostile strings in every accepted text field; use enums/strict identifier validation rather than a regex-only secrecy promise.
- Record operation transitions, not every `/api/state` poll or audio-level update. Browser submissions: at most 30 events/minute per app instance, body <=8192 bytes; duplicates within 60 seconds aggregate a bounded count. Rate limits use a monotonic clock.
- Serialize threads with a lock. Protect fixed log files across CLI/app processes with an OS lock (stdlib fcntl/msvcrt), acquired nonblocking; on contention keep the event in the bounded memory ring. The empty lock file contains no diagnostic data and must not be rotated/replaced while locked. Do not import the server into the diagnostics module.
- Use atomic replacement for each log/backup write. Rotation may lose an oldest segment on crash, but must not corrupt the current committed segment or affect application data. Export revalidates every event; ignore partial/corrupt/oversized/symlinked segments and disclose omission.
- Export ZIP <=2097152 bytes, with only `summary.txt`, `manifest.json`, `events.jsonl`, `test-results.json`. It is built in memory. CLI writes it atomically; HTTP returns bytes without a persistent export file. CLI retains at most three generated bundles under `data_dir()/reports` and does not delete unrelated files.
- Summary uses fixed English explanations/next checks for stable codes; no arbitrary exception text. Include diagnostic storage degradation and omitted-event counts. Keep raw `doctor-report.txt` out: the existing report contains absolute paths.
- Diagnostics capture during startup is best effort. Use minimal imports before diagnostics initialization where practical; syntax/import failures occurring before initialization are a stated gap, with the same launcher fallback.

### Interfaces to freeze before handoffs

Create `tf2reaudio/diagnostics.py` with `DiagnosticsError` and:

- `DiagnosticRecorder(root: Path)`; dependency-free with respect to app/server/game modules.
- `record(component: str, action: str, outcome: str, code: str, *, operation_id: str | None = None, details: dict | None = None, error: BaseException | None = None) -> None`.
- `snapshot() -> dict`: sanitized events, persistence status and omission counters; never raises for log I/O failures.
- `build_bundle(snapshot: dict, checks: dict, test_results: list[dict]) -> bytes`: validates the contract and returns the bounded ZIP or raises DiagnosticsError.
- `save_bundle(root: Path, data: bytes) -> Path`: atomic save with report retention, readable DiagnosticsError on failure.

Recorder instances for the same root within a process share their writer/lock/session and expose the same snapshot. Logging code never reads settings/group files to discover secrets. Callers build sanitized structured `checks` (versions, fixed statuses, capability booleans, counts) using existing public APIs. There is no generic "add arbitrary metadata" escape hatch.

`POST /api/diagnostics/event`: strict enum schema, local Host/Origin/X-TF2RA checks, body/rate limits; 204 success, 400 invalid, 413 oversized, 429 throttled. New diagnostic routes exist on the local UI server only, never on SyncServer/tunnel.

`POST /api/diagnostics/export`: JSON `{test_results: [...]}`, at most 11 checklist entries, one per step; no output path accepted. Returns application/zip, Content-Disposition with a generated basename, existing security/no-store headers. Export is allowed before TF2 setup and when game/group initialization fails. Gathering status never applies voices, repairs data, starts TF2 or starts hosting.

Browser interface: `window.Diagnostics.emit(action, outcome, code, details = {})`, `window.Diagnostics.results()`, `window.Diagnostics.exportFallback()`. Its queue is memory-only, <=100 validated events; submission timeout 2 seconds, no automatic retry loop. Diagnostic endpoint failures never emit diagnostic endpoint events. A server-disconnected fallback downloads an explicitly labeled browser-only JSON report; the CLI bundle remains the way to retrieve persisted backend events.

## File map and ownership handoffs

| Item | Owner | Files/responsibility |
|---|---|---|
| D1 | New diagnostics owner, register in TASKS.md first | Create `tf2reaudio/diagnostics.py`, `tests/test_diagnostics.py`; privacy, event storage, bundle generation |
| D2 | T10, with T14 handling run/host startup section | `tf2reaudio/__main__.py`, `tests/test_cli.py`; initialization, command errors, doctor bundle |
| D3 | T14 | `tf2reaudio/server.py`, `tests/test_server.py`; API boundaries and local diagnostic endpoints |
| D4 | T15 | Create `tf2reaudio/web/diagnostics.js`; modify `web/index.html`, `web/app.js`, `web/strings.js`, `tests/test_web.py`; UI, browser collector and acceptance tests |
| D5 | T16/T17/T18, each only their own file | `web/recorder.js`, `web/setup.js`, `web/group.js`; actual caught failure/transition signals |
| D6 | T6 | `TF2ReAudio.cmd`, `tf2reaudio.sh`, `docs/launchers.md`; pre-Python failure codes and support instructions |
| D7 | T19 + T0 for version only | `tools/build_zip.py`, `tests/test_build_zip.py`, `docs/README.md`, `docs/local-ui-review.md`; T0 `tf2reaudio/__init__.py`; tested next preview |

Paths abbreviated with `web/` above are under `tf2reaudio/web/`. Do not modify game/store/sync/group internals just to add logs in v1; observe their results at CLI/API/UI boundaries. Background sync state changes must also be captured through a lightweight local-server observer using the existing status fields, without performing network requests.

## D1 — Structured recorder and support archive

**Depends on:** ownership registration only. **Produces:** all Python interfaces above.

- [ ] Register the new files with the task coordinator; keep existing ownership intact.
- [ ] Add unittest cases `test_unknown_fields_and_sensitive_strings_never_reach_disk_or_export`, `test_rotation_bounds_four_files`, `test_threads_and_two_processes_do_not_corrupt_lines`, `test_failed_replace_preserves_primary_and_memory_events`, `test_readonly_logs_do_not_break_record`, `test_export_during_rotation_is_valid`, `test_oversized_corrupt_or_symlinked_logs_are_omitted`, `test_bundle_retention_keeps_three_owned_files`. Assert caps above, inspect every ZIP entry and decompress every text entry when checking secret absence. Test long Unicode fields, malicious event identifiers and CR/LF injection.
- [ ] Run `python -m unittest tests.test_diagnostics -v`; observe the expected missing-behavior failures.
- [ ] Implement the frozen API, schema/enum validation, fixed code explanations, locks, atomic rotation, memory fallback and safe archive generation. Test with injected ENOSPC, PermissionError and replacement failure; do not use real disk exhaustion.
- [ ] Re-run D1 tests; require all pass, then commit only the registered D1 files.

## D2 — CLI support even when the UI/TF2 is unavailable

**Depends on:** D1. **Consumes:** recorder/build_bundle/save_bundle. **Produces:** `doctor --bundle` and sanitized startup/CLI operation events; existing `doctor --copy` remains compatible.

- [ ] Add CLI tests proving missing TF2 still produces a valid bundle, existing `--copy` behavior remains intact, denied export prints a readable error, and an unexpected exception produces a safe diagnostic fault without printing a traceback. Use temporary XDG_DATA_HOME/APPDATA and fixture installs only.
- [ ] Add a concurrent app/doctor test: doctor bundle creation does not acquire the app lifetime lock, corrupt logs or shut down the app. Ensure independent export works with no running server.
- [ ] Run `python -m unittest tests.test_cli -v`; verify the new tests fail for the missing flag/behavior.
- [ ] Initialize the recorder once a command is parsed, before opening game/store/server objects. Add `--bundle` only to doctor. Separate sanitized check collection from the raw text doctor report; do not include a text report containing paths. Log setup only as a fixed operation result, never copied launch options/stdout. T14 handles run/host lifecycle events in its owned section.
- [ ] Define exit behavior: successful bundle creation returns 0 even if checks report missing TF2; failed bundle creation returns 1. Existing doctor without --bundle keeps its exit behavior. Print report destination locally; exclude that path from exported content.
- [ ] Run CLI + D1 tests and commit the T10/T14 sections through their owners.

## D3 — Protected API diagnostics and operation outcomes

**Depends on:** D1. **Consumes:** recorder/build_bundle and existing app status APIs. **Produces:** the two local POST endpoints above.

- [ ] Add server tests for no-TF2 export; rejected foreign Host/Origin/missing X-TF2RA; oversized and invalid event bodies; 31st event/minute throttled; no arbitrary paths; invalid checklist values rejected; diagnostic routes absent from sync server.
- [ ] Add tests for injected save PermissionError, storage error, RCON game-closed/auth failure and unexpected request exceptions. Assert stable codes and numeric OS errors in records, useful HTTP errors for the user, no passwords/paths/request payloads in logs. A 200 response with `install_error` or unsuccessful apply result is not logged as success.
- [ ] Add snapshot/export concurrency tests, occupied-port exhaustion/startup events, thread failure capture without raw traceback leakage, and background sync status transitions. Repeated unchanged state does not generate repeated events or make additional network calls.
- [ ] Run `python -m unittest tests.test_server -v`; verify new behavior fails before implementation.
- [ ] Add startup/start-result/stop and API operation events, strict endpoints and a stop-aware status observer on the existing server lifecycle. Use route enums rather than raw URLs, sanitized error types rather than response bodies. Export outside the app mutation lock after taking a short consistent snapshot. Use a safe global/thread exception hook only when installed/restored by the app lifecycle; never swallow KeyboardInterrupt/SystemExit.
- [ ] Re-run server, CLI and diagnostics tests, then commit only T14 files.

## D4 — Browser collection and one-click export

**Depends on:** D1/D3. **Consumes:** both local endpoints. **Produces:** frozen window.Diagnostics API and settings diagnostics panel.

- [ ] Add browser checks for unsupported getUserMedia/MediaRecorder, denied permission, failed save, unexpected JS error, offline backend, diagnostic request failure without recursion, keyboard-accessible export and selected manual outcomes. Assert no device labels, pasted invitation, launch password, URL fragment or arbitrary exception message is persisted/exported.
- [ ] Exercise real ZIP download, parse it in Python and check entries/content; a visible button alone is not success. Verify byte cap and correct not_tested defaults. Simulate a backend disconnect and verify the browser-only fallback labels its missing backend evidence.
- [ ] T15 updates the existing hosting test fixture from `friends.example` to an allowed fake Quick Tunnel origin and its matching expected invitation URL, preserving the security allowlist. The v0.1.0 browser run had 15/16 passing; this is an existing fixture issue, not evidence all browser checks currently pass.
- [ ] Run the new acceptance tests with existing TF2RA_PLAYWRIGHT/TF2RA_BROWSER; verify expected failures before implementation. Do not install dependencies/download browsers.
- [ ] Implement diagnostics.js before other application scripts; retain only validated structured capability/error codes. Add global error/unhandledrejection handlers that never submit raw messages/stacks/URLs. Instrument API failures without recursively using the logged request wrapper for diagnostic requests.
- [ ] Add **Diagnostics**, **Download diagnostic report**, **Download browser-only report** and fixed checklist/reason labels to strings.js. Download includes backend snapshot plus flushed client events when connected; UI explains manual sharing and exclusions. Keep content visible/focusable if setup is incomplete.
- [ ] Re-run all browser checks and server tests, then commit T15 files only.

## D5 — Record failures where the UI currently catches them

**Depends on:** D4. **Consumes:** window.Diagnostics.emit. **Produces:** microphone/preview/save/restore/backup/sharing operation transitions.

- [ ] Through T15's acceptance-test owner, add failing browser checks for microphone busy/missing/denied/timeout, unsupported AudioContext, decode failure, preview play rejection, save failure, import/export failure and offline sharing. Successful recording never implies successful preview/apply/hearing.
- [ ] T16 instruments acquire/start/stop/decode/report with stable failure codes before errors are translated to user messages. T17 instruments settings, connection test, restore, backup/import and diagnostic export binding using the D4 helper. T18 instruments join/host/manual sync result transitions without sending group names, invite text or links.
- [ ] Keep each owner within its file; request changes in shared tests from T15. Do not change capture, trimming, saving or synchronization behavior as part of logging.
- [ ] Run the affected browser checks, then the full suite. Commit per owner after passing checks; disclose skipped checks.

## D6 — Launcher failure reporting before Python exists

**Depends on:** the design contract; can be prepared independently of D1. **Produces:** safe visible stage codes and a fallback a Windows tester can use without the app.

- [ ] Define codes `BOOT_FOLDER`, `BOOT_NOT_EXTRACTED`, `BOOT_PYTHON_MISSING`, `BOOT_DOWNLOAD`, `BOOT_HASH`, `BOOT_EXTRACT`, `BOOT_IMPORT`, `BOOT_APP_EXIT`; retain existing clear explanations, pause behavior and exit codes. Do not persist raw curl/PowerShell output or the launcher's stdout stream, since setup output can contain passwords.
- [ ] Document copying the code/last completed step and sending a screenshot with personal paths/credentials obscured; Python-independent automatic log files are explicitly out of scope for this version. A screenshot is a manual fallback, not a ZIP log.
- [ ] Test existing and new failure branches with controlled commands on native Windows, covering no Python, offline download, hash mismatch, denied extraction and a path with spaces/non-ASCII. Use a disposable local fixture harness; no real download or real TF2 in unittest. Linux checks cover missing Python and a read-only program folder.
- [ ] Keep launcher changes under T6. A Python unittest that only searches the .cmd text is insufficient. Native Windows checks stay Not run until executed and recorded with OS/build identity.
- [ ] Record the remaining pre-Python automation gap: automatic persistence here would require a bootstrap mechanism and an explicit exception to the current util.atomic_write rule. Do not silently implement a PowerShell writer under this plan.

## D7 — Extracted-package validation and next preview handoff

**Depends on:** D1–D6. **Consumes:** finished product and reports. **Produces:** tested local candidate and maintainer handoff; publication is a later execution action.

- [ ] Add packaging regression tests: diagnostics.py/diagnostics.js are present, support guides are included, and logs/reports/tester bundles/settings/tokens/audio never enter the program ZIP. Test extracted `doctor --bundle` against fake TF2 and no-TF2 setups from a path containing spaces.
- [ ] Run the new tests red, then adjust packaging/docs minimally. T0 updates version to 0.1.1 once integration is complete; protocol version remains 1 because diagnostics endpoints are local-only. Do not overwrite published v0.1.0 assets.
- [ ] Run `python -m unittest`; require zero failures and list every skip. Run all existing Chromium checks separately using configured local tools. Require zero browser failures, including the corrected host fixture.
- [ ] Build twice with `python tools/build_zip.py`; verify identical bytes, archive integrity, extraction startup and absence of tester data. Downloading/uploading release assets is not a unit test and is not performed in this planning session.
- [ ] Native Windows 10/11 acceptance: clean launch without Python, record/deny microphone, simulate blocked file replacement, close TF2 before apply, reproduce a failed operation, download the report, reopen ZIP and verify the last operation/code matches what happened. Also test CLI export with the local server stopped and the pre-Python manual fallback. Record OS/Python/browser/build versions and exact candidate SHA-256.
- [ ] Linux acceptance repeats record/save/apply/restore/report export with isolated fixtures plus a human real-game check where available. Clearly separate automated fixtures from physical microphone/game evidence.
- [ ] Review exported reports for secret/path absence before asking testers to share them. The maintainer should identify the failing step and next check from summary.txt without opening source code.
- [ ] Hand off source identity, candidate hash, test outcomes, known gaps and owner requests. A future published preview must disclose remaining Windows/real-game/network limits.

## Definition of done for the future implementer

- [ ] A tester can export a useful ZIP from settings or CLI with TF2 missing and with the server stopped (CLI).
- [ ] The last failed operation is attributable to a stable code, source and session; unsupported/not_tested/manual claims are distinguished correctly.
- [ ] Failures to write logs do not break the operation being diagnosed, and export discloses degraded evidence.
- [ ] Disk retention and archive limits hold under concurrent use; no unrelated files are deleted.
- [ ] Secret absence is checked before persistence and across every decompressed export entry.
- [ ] Native Windows outcomes are recorded, or explicitly remain Not run. Passing Linux tests is not Windows certification.
- [ ] TASKS.md owners deliver only their assigned sections/files. No game/store/sync protocol changes are needed.

## Planning-session report

Only this plan was created. Existing code, tests, configuration, TASKS.md ownership,
release assets and game data were not modified. The plan was checked against current
entry points, storage rules, module ownership, packaging behavior and the known
Chromium fixture failure. No product tests, native Windows checks or implementation
work were performed for this planning-only change. All work items remain pending.
