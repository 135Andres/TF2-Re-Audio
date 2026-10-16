# Local closure: assignments for separate agents

Prepared 2026-10-15 from `PLAN.md` v5, `TASKS.md`, the UX audit, the local review, and the Wave 2 record. These are work orders, not completion claims. Give an agent access to the repository plus one assignment; do not send the assignment without the referenced source documents.

## Current checkpoint

The latest recorded full Linux/Chromium run executed 192 tests, with one keyboard-focus failure after saving a variant and two skips. The previous run of 191 tests passed. These historical counts are not targets for a new run. The implementation already includes local recording/recovery, security headers and bounded ZIP import/backup-safe cleanup. Do not rebuild those features from scratch.

The remaining acceptance gap is physical microphone recording, replacements heard in real TF2, RCON/apply during Casual, native Windows, and broader user/accessibility testing. Reading original audio successfully does not close that gap.

## Dispatch and ownership

| Assignment | Existing owner | Allowed existing files | Start condition |
|---|---|---|---|
| [01: keyboard focus](01-keyboard-focus.md) | T15 | `tf2reaudio/web/app.js`, `index.html`, `style.css`, `strings.js` in the same directory; `tests/test_web.py` | Now |
| [02: storage failure recovery](02-storage-recovery.md) | T8 | `tf2reaudio/store.py`, `tests/test_store.py` | Now, independently of 01 |
| [03: Linux validation](03-linux-validation.md) | Human milestone; documentation only | None; new Linux report only | Preparation now; final observations after 01/02 and 05 |
| [04: Windows validation](04-windows-validation.md) | Human milestone; documentation only | None; new Windows report only | Preparation now; execution after Linux is stable and 05 identifies a candidate |
| [05: private candidate](05-private-candidate.md) | T19 | `tools/build_zip.py`, `tests/test_build_zip.py`, `docs/README.md`, `docs/local-ui-review.md` | Documentation preparation now; final build after 01/02 |
| [06: integration and status](06-integration-status.md) | Documentation coordinator | `PLAN.md`, `TASKS.md`, `AUDITORIA_UX.md`, `docs/milestone-wave2.md` | Baseline now; final integration after agent reports |

All short web filenames in the table are under `tf2reaudio/web/`. Each agent also owns only the new report path stated in its assignment, under `docs/agent-reports/`. No agent edits another agent's brief or report.

01 and 02 can implement concurrently. 03 and 04 can prepare evidence sheets concurrently without touching the game. 05 must build from a stable integrated snapshot, never while 01/02 are writing. 06 verifies that snapshot; it does not silently fix other owners' code. Use separate branches/worktrees where available and integrate explicitly; with a shared checkout, obey these file boundaries and serialize final build/test operations. An agent can finish its preparation while leaving a human-dependent result pending.

## Copyable dispatch message

> Read AGENTS.md, PLAN.md, TASKS.md, docs/superpowers/plans/2026-10-15-local-closure/README.md and docs/superpowers/plans/2026-10-15-local-closure/<assignment>.md. Execute only that assignment. Respect file ownership, use existing dependencies only, preserve unrelated changes, and write its assigned report. Separate automated evidence from human observations and list checks not run. Do not start group/sync, publish anything, or edit another task's files.

Replace `<assignment>` with one filename from the table. Do not dispatch 06 as permission to edit implementation files.

## Gates and deferred work

1. 01 resolves or accurately diagnoses the recorded focus failure; the configured full browser suite passes.
2. 02 establishes the specified storage failure behavior or reports the precise external dependency preventing closure.
3. 05 creates a reproducible private candidate with source identity and checksum; 06 records the integrated suite result.
4. A human completes 03 with a physical microphone and real Linux TF2. Fixtures cannot substitute for this.
5. A human completes 04 on native Windows using an identified candidate. Fixes are routed to the existing module owner and affected checks repeated.
6. Only after required Linux and Windows real-game checks pass may the existing T11→T12→T13→T18 collaboration sequence begin. These briefs do not authorize it. The five-person study and full accessibility acceptance also remain pending.

This batch covers local closure and storage fault checks recommended before networking. It does not promise to implement every proposal in PLAN §13: persistent logging, expanded diagnostics, future group security, localization and optional convenience features need separately scoped work if adopted. English-only UI and private distribution remain the current decisions.
