# Linux: local workflow and real-game evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task when available. Steps use checkbox (`- [ ]`) syntax for tracking. This is a single-agent assignment; do not delegate additional work.

**Goal:** Prepare and record reproducible Linux acceptance evidence without substituting fixtures for physical microphone or in-game observations.

**Architecture:** Use the existing milestone protocol and private candidate. The agent prepares and records; the human performs microphone listening and real-game interaction.

**Tech Stack:** Python >=3.10 standard library, unittest, local HTML/CSS/JavaScript; existing optional Chromium/Playwright only where specified.

**Spec:** `docs/milestone-wave2.md`, especially A, D and E; `PLAN.md` Linux-first decision.

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

Create only `docs/agent-reports/03-linux-validation.md`. Read existing documentation and code as needed; do not edit implementation, tests, launchers, milestone docs or app settings as part of preparation.

Consume the source revision, ZIP path/checksum and test evidence from 05/06. Produce a per-step evidence sheet and owner-specific defect requests. Preparations may start now; final candidate observations wait for the stable candidate. The physical session requires the user to participate; do not start a game, overwrite recordings or send real RCON commands unattended.

## Review Focus

- A stale `tf2reaudio_test` mod masks the new sound: record its presence before any human removal.
- The browser decodes an original but nobody hears a replacement: keep these as separate checks.
- First installation needs a full TF2 restart: record that restart explicitly.
- RCON connects in menu but times out or stutters during Casual: record each phase separately.
- Restore or Undo appears correct in UI but not in game: verify the actual heard result.

## Steps

- [ ] Create a sheet with date, source commit/dirty state, candidate checksum, Linux distribution, Python/browser versions and tester. Initialize every actual-use outcome as `Not run`.
- [ ] Record current automated evidence by reference to 06, and separate historical archive-reading/browser checks from observations made for this candidate.
- [ ] Prepare the human web sequence: open candidate, choose TF2, inspect test-mod warning, select Soldier/MEDIC!, choose a physical mic, record, preview, Save, restart TF2 once, hear the replacement, then recover the prior selection with History/Undo and check it again. Export a collection backup before changing existing recordings. Never include launch options or credentials in the report.
- [ ] Prepare and, with the human, follow `docs/milestone-wave2.md` A and D for the CLI/RCON/Casual checks. Use two audibly different short recordings or test WAVs. Record connection timeouts, whether the new sound is heard after apply, audio recovery and estimated stutter duration for two attempts.
- [ ] Record each Review Focus outcome with `Pass`, `Fail` or `Not run`, the observation, and candidate identity. A local map does not count as Casual. A sent RCON command does not prove a heard replacement.
- [ ] Route defects: UI focus T15; mic/conversion T16/T4; settings T17/T14; real RCON T3; installation/restore T9; discovery T1. Give exact reproduction and redacted error; do not fix their files here.
- [ ] Finish the preparation report even if a human is unavailable, marking acceptance pending and listing the exact remaining actions. Send completed evidence to 06; do not declare Wave 2 complete.

## Acceptance

The deliverable is an honest, candidate-specific report. Linux real-use acceptance requires human-confirmed physical recording, replacement playback, restore/recovery and the required real-game/RCON checks; preparation alone does not pass them. Windows remains a separate gate.
