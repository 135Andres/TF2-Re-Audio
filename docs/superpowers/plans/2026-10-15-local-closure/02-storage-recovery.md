# T8: collection durability under write failures Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task when available. Steps use checkbox (`- [ ]`) syntax for tracking. This is a single-agent assignment; do not delegate additional work.

**Goal:** Prove that failed collection writes preserve the last committed collection and recoverable audio, and fix T8-local defects found by those tests.

**Architecture:** Extend existing Store failure tests using injected failures around atomic_write. Keep the collection format, ZIP limits and backup-aware garbage collection unchanged.

**Tech Stack:** Python >=3.10 standard library, unittest, local HTML/CSS/JavaScript; existing optional Chromium/Playwright only where specified.

**Spec:** `TASKS.md` T8; `PLAN.md` §10 and §13.5; `tests/test_store.py` existing failed-write and backup tests.

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

Modify only `tf2reaudio/store.py` and `tests/test_store.py`. Create `docs/agent-reports/02-storage-recovery.md`.

Consume `util.atomic_write(path, data: bytes) -> None`; do not edit `util.py` or `tests/test_util.py` (T0). Preserve `Store.add_take`, `set_active`, `snapshot`, `blob`, `export_zip`, `import_zip` and reopen behavior. Use the actual Store exception hierarchy. Module-owned expected error handling must remain clear and must not lose the original cause.

## Review Focus

- ENOSPC during backup rotation must preserve the prior committed primary and its referenced audio.
- Failure during primary persistence after backup rotation must leave a reopenable prior state.
- A failure while writing a new blob must not commit a take referencing a partial/missing blob.
- A failed selection must not appear successful in memory and disappear on restart.
- Garbage collection after a failed write must not delete audio reachable from the durable primary or backup.

## Steps

- [ ] Read `_save`, `_commit`, `add_take`, `_drop_blobs` and the existing `test_failed_write_leaves_no_temp_files`. Run `python -m unittest tests.test_store -v` to establish the baseline.
- [ ] Add targeted unittest cases named for backup-write ENOSPC, primary-write ENOSPC, blob-write failure, failed-selection rollback, and failure-plus-GC protection. Use temporary folders and `OSError(errno.ENOSPC, ...)`; inject at the actual intended write, not every call indiscriminately.
- [ ] For each failure, compare the pre-operation snapshot with a newly reopened Store; assert every referenced blob remains readable and no partial/temp output is treated as committed. For selection rollback assert the live instance agrees with reopened state. For a failed blob addition assert the take is absent. A valid unreferenced complete blob may be retained for later cleanup.
- [ ] Where tests reveal a defect, capture the failing output first and apply a minimal T8 fix. Do not add a schema version, change retention counts, or relax ZIP/path validation. If the defect is in atomic_write itself, report a T0 request and keep that acceptance item open.
- [ ] Run `python -m unittest tests.test_store -v` and `python -m unittest tests.test_game tests.test_server tests.test_cli -v`. Report exact results and any known unrelated failures.
- [ ] Write the report and identify remaining physical power-loss/filesystem risks. Simulated exceptions establish failure behavior; they do not prove hardware power-loss durability or native Windows locking.

## Acceptance

The five injected failure classes have explicit assertions and preserve recoverability. Existing format compatibility, double-corruption protection, ZIP limits, retention and backup-only audio tests pass. No real filesystem is filled and no real TF2 data is touched.
