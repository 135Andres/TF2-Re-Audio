# T8 storage write-failure recovery

Date: 2026-10-15. Environment: Linux, Python 3.14.8.
Source commit: `b7f9f3b330d8caae743b8e1e93964c8cfea5cd0c`.

## Scope and working tree

Read AGENTS.md, PLAN.md, TASKS.md, the local-closure README and assignment 02. Changed only `tf2reaudio/store.py`, `tests/test_store.py`, and this report. No commit or publication was requested or performed.

At baseline, unrelated changes were `AUDITORIA_UX.md` and untracked `docs/superpowers/`. During validation, unrelated modifications to `tests/test_web.py`, `tf2reaudio/web/app.js` and `docs/milestone-wave2.md` also appeared. Those files were left untouched. The results below concern the commands actually run here, not historical full-suite results.

## Changes and observations

Added five targeted unittest cases, with nine failure subcases:

- Backup-write ENOSPC: primary and previous backup remain byte-for-byte intact; the failed take is absent from both the live and reopened snapshots.
- Primary-write ENOSPC after backup rotation: primary remains intact and backup equals the last committed primary. Subsequent deliberate primary corruption recovers the same snapshot from backup.
- Blob-write failure, with and without an existing collection: no take or final audio file is committed.
- Failed selection at local-state, backup and primary persistence: active selection, snapshot, history and visible state agree in memory and after reopening. A retry then persists successfully.
- Failure while pruning, at backup and primary persistence: rollback preserves committed takes; subsequent garbage collection retains exactly the union of primary and current-backup audio references.

Injection targets the selected destination in the real atomic writer's `os.replace`, raising `OSError(errno.ENOSPC, ...)` after the temporary file exists. Other writes proceed normally. Tests verify cleanup of temporary files and SHA-256 readability of every audio blob referenced by the primary and backup. A complete orphan blob after failed metadata persistence is allowed and is removed safely by later cleanup.

The existing rollback and backup-aware cleanup passed these checks. The new tests initially exposed raw OSError propagation: five tests failed with nine error subcases. Applied a minimal fix to convert persistence errors in `_save` and new-audio errors in `add_take` into StoreError with clear English messages and the original exception as `__cause__`. Updated the existing failed-write test to require StoreError. No collection format, retention count, ZIP validation or atomic-write implementation changed.

## Commands and results

- Baseline: `python -m unittest tests.test_store -v` — 29 tests, OK, no skips (0.974 s).
- Before fix: `python -m unittest tests.test_store.WriteFailureTest -v` — 5 tests, FAILED, 9 error subcases (raw ENOSPC).
- After fix: `python -m unittest tests.test_store -v` — 34 tests, OK, no skips (1.247 s). Includes existing format compatibility, double-corruption, ZIP limits, retention and backup-only audio checks. The deliberate duplicate ZIP-entry fixture emits its existing UserWarning.
- `python -m unittest tests.test_game tests.test_server tests.test_cli -v` — 59 tests, OK, no skips (14.948 s), using fixtures and loopback fake servers.
- `git diff --check` — passed.

## Not run and remaining risks

Native Windows: Not run. Windows file locking and access-denied behavior remain unverified. Physical power loss, filesystem/device failure, actual disk exhaustion and process termination: Not run. These tests simulate exceptions at atomic replacement; they do not simulate short writes, flush/fsync failures, or prove hardware power-loss durability. No real TF2 files, microphone, game session or external network were used. Full repository/browser suite: Not run; this assignment's required storage and consumer suites passed.

## Requests to other owners

No cross-module implementation changes are required by the observed failures. T0 (`tf2reaudio/util.py`) remains the owner for any future physical durability work or defects found inside atomic_write; no such defect was established here. Native Windows and real-game acceptance remain with the human milestone assignments. The unrelated web changes require their own owner's validation.
