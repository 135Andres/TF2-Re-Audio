# T15: keyboard focus after saving a variant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task when available. Steps use checkbox (`- [ ]`) syntax for tracking. This is a single-agent assignment; do not delegate additional work.

**Goal:** Restore useful keyboard focus after the recorder closes, including when the edited variant row is recreated.

**Architecture:** Keep the existing local UI and APIs. Diagnose dialog closure and asynchronous line rendering in app.js before changing focus handling; preserve variant-only installation.

**Tech Stack:** Python >=3.10 standard library, unittest, local HTML/CSS/JavaScript; existing optional Chromium/Playwright only where specified.

**Spec:** `TASKS.md` T15; `PLAN.md` §1 and §8; `tests/test_web.py` variant scenario.

## Global Constraints

Read `AGENTS.md`, `PLAN.md`, `TASKS.md`, and this folder's `README.md` before work. The existing task ownership is authoritative; this brief narrows that ownership and does not transfer files between tasks.

- Python >=3.10, standard library only. No `pip install` or dependency downloads.
- Windows and Linux: use `pathlib`; specify `encoding="utf-8"` and `newline` for text I/O.
- All persistent data writes go through `util.atomic_write`, including generated reports.
- User-visible text is in English. Expected errors use the module's own exceptions and clear messages; no user-facing tracebacks.
- Automated tests use `unittest`, temporary fixtures, and fake servers on `127.0.0.1` with port 0. They must not access real TF2 or the external network.
- Keep the project private. No publishing, public downloads, license selection, group/sync work, or automatic apply.
- Do not revert unrelated edits, especially the existing change to `AUDITORIA_UX.md`. Do not stage or commit another agent's files.
- Implement only the assigned scope. Report a required cross-module change to its owner; do not edit that module yourself.
- Do not infer human acceptance from automated tests. Record unavailable checks as `Not run`.

## Delivery report

Write only your assigned report. Include the source commit and dirty files, changes, exact commands and results, skips and missing environments (especially native Windows), remaining risks, and requested changes with owning T-number and file. Distinguish observations made now from historical results. Do not include passwords, tokens, or copied Steam launch options. Commit only explicitly assigned files if committing is requested; do not merge or publish.

## Files and interfaces

Modify only `tf2reaudio/web/app.js`, `tf2reaudio/web/index.html`, `tf2reaudio/web/style.css`, `tf2reaudio/web/strings.js`, and `tests/test_web.py`, as needed. Create `docs/agent-reports/01-keyboard-focus.md`.

Read `tf2reaudio/web/recorder.js` but do not edit it (T16). Consume the existing recorder callbacks and local API; produce the same API calls and persisted variant selection. If T16 changes are required, report the exact callback/contract issue.

## Review Focus

- A line re-render replaces the original trigger: restore focus to the current equivalent control.
- A variant sits inside closed Details: the focus destination must be visible and usable.
- Escape or Discard closes the recorder without saving: focus returns and no take is created.
- A failed save leaves the recording recoverable and focus within the open dialog.
- Closing after a whole-line edit must not regress while fixing variant edits.

## Steps

- [ ] Record `git status --short` and inspect `WebTest.test_variant_recording_and_keyboard_zoom`, the `variant` browser scenario, dialog close callbacks and line rendering. The exact current failure must be reproduced, not assumed from PLAN.
- [ ] Locate an existing Playwright Node package and Chromium. Set `TF2RA_PLAYWRIGHT` and `TF2RA_BROWSER` to their actual paths. If unavailable, report the missing environment; do not claim the focus failure passed from a skipped run.
- [ ] Run `python -m unittest tests.test_web.WebTest.test_variant_recording_and_keyboard_zoom -v` with those variables. Save the assertion and observed active element.
- [ ] Strengthen/add focused scenarios in `tests/test_web.py`: immediately after Save, assert the active element is connected, visible and associated with the edited line/variant; press Tab and assert it reaches a usable control. Cover the five Review Focus cases using the existing fake mic and temporary TF2 setup. Verify that the regression assertion fails before the fix. Avoid fixed extra sleeps as the fix.
- [ ] Apply the smallest T15 change to restore focus after asynchronous rendering. Do not weaken installation, mic lifecycle, CSP, keyboard or zoom assertions.
- [ ] Run `python -m unittest tests.test_web -v` with Chromium enabled. Verify variant #02 is installed while the whole-line selection remains untouched and #01 is absent, as already asserted by the test.
- [ ] Write the report with reproduction, cause, changed files, exact test result and browser paths/versions. Send the source revision to 05/06. Full-suite verification is performed on the stable integration by 06.

## Acceptance

The reproduced focus regression passes without deleting or weakening checks; Save, cancel/Escape, failed save and whole-line recording retain usable focus. Real microphone and Windows results remain explicitly unverified unless actually observed.
