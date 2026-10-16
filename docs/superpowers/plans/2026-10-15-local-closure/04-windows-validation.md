# Windows: native candidate validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task when available. Steps use checkbox (`- [ ]`) syntax for tracking. This is a single-agent assignment; do not delegate additional work.

**Goal:** Prepare native Windows checks and record their actual results after Linux is stable.

**Architecture:** Use the shipped Windows launcher and existing guides. The agent creates an evidence sheet; a human with Windows 10/11 x64 runs it against an identified private candidate.

**Tech Stack:** Python >=3.10 standard library, unittest, local HTML/CSS/JavaScript; existing optional Chromium/Playwright only where specified.

**Spec:** `docs/launchers.md` Windows checklist; `docs/milestone-wave2.md` B–D; `TASKS.md` Wave 2 gate.

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

Create only `docs/agent-reports/04-windows-validation.md`. Do not edit the launcher (T6), packaging (T19), RCON (T3), game bridge (T9), or other owners' files. Consume 05's candidate checksum and 03/06's Linux status.

Preparation can happen now. Do not execute the Windows acceptance session until Linux is stable and a candidate is identified. Linux mocks, Wine and code inspection cannot establish native Windows acceptance. If no native Windows tester exists, deliver the prepared checklist with every actual-use item `Not run`.

## Review Focus

- No Python, only Store alias, or existing supported Python: record launcher selection and whether the browser opens.
- Extraction under a path containing spaces and symbols: the packaged app must still launch.
- Download unavailable or checksum mismatch: preserve a readable error, without claiming a successful installation.
- TF2 holds a target file open: record the precise replacement error and retry after closing TF2.
- Microphone permission and playback differ from Linux: test a physical Windows mic and actual heard audio.

## Steps

- [ ] Create a sheet with `winver`, architecture, Python/runtime, browser, tester, date, source commit and candidate checksum; initialize all outcomes to `Not run`.
- [ ] Adapt the existing launcher checklist without copying its obsolete stub expectations: `run` now exists, so success is the local browser UI opening, not `Not implemented yet`. Flag that documentation correction for 06, which owns consolidation of the guides through a T6 request if necessary.
- [ ] Have the human follow the guide's fresh runtime/existing Python, repeat launch, special-character path, cmd/PowerShell and failure scenarios in an appropriate disposable environment. A fresh-runtime download is a manual installation check, outside the offline automated suite. Do not change the user's primary Python installation to manufacture a case.
- [ ] Have the human perform milestone B and D and physical mic recording/preview/Save. Separately record real RCON, first playback after restart, replacing while TF2 runs, Casual apply, heard new sound, repeated apply and audio/stutter observations. Do not mark a local-map result as Casual.
- [ ] For access-denied/locked-file errors, capture redacted exact text and whether the same import succeeds with TF2 closed. Route the defect to T9/T0 rather than modifying their files.
- [ ] Write the evidence and owner-specific requests: T6 launcher; T1 discovery; T3 RCON; T9 replacement; T16 mic; T14 server. Send results to 06. Leave missing cases pending.

## Acceptance

Prepared checklist delivered; execution is complete only when required native checks have recorded outcomes tied to the candidate. Windows results are never inferred from Linux. This assignment neither publishes a ZIP nor enables collaboration or automatic apply.
