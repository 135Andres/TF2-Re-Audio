# Integration: evidence and project status Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task when available. Steps use checkbox (`- [ ]`) syntax for tracking. This is a single-agent assignment; do not delegate additional work.

**Goal:** Consolidate agent results into an accurate status and preserve the real-game and Windows gates.

**Architecture:** Coordinate a stable source snapshot, verify it without editing implementation, then reconcile historical documentation with current evidence.

**Tech Stack:** Python >=3.10 standard library, unittest, local HTML/CSS/JavaScript; existing optional Chromium/Playwright only where specified.

**Spec:** `PLAN.md` §1, §9 and §13; `TASKS.md` ownership and execution gate; reports 01–05.

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

Modify only `PLAN.md`, `TASKS.md`, `AUDITORIA_UX.md`, and `docs/milestone-wave2.md`. Create `docs/agent-reports/06-integration-status.md`. Preserve the existing uncommitted audit note and historical findings. Do not edit implementation, tests, `docs/local-ui-review.md`, `docs/README.md` or `docs/launchers.md`; request T19/T6 changes instead.

Consume the five reports plus commit/diff identities and candidate checksum. Produce a current state table, unresolved owner-specific requests and gate decision. Do not automatically cherry-pick/merge branches without reviewing scope and coordinating the integration method with the working session; never overwrite another checkout's dirty work.

## Review Focus

- A plain unittest run skips browser tests: report browser acceptance separately.
- Historical audit language says the web does not exist: label its date and add a current follow-up.
- Storage recommendations are described as missing despite integrated fixes: link evidence rather than reopen completed work.
- A human test refers to a different candidate: retain that identity and request the affected recheck.
- A pending environment is recorded as a pass: use explicit `Not run`, not an inferred success.

## Steps

- [ ] Record the starting commit, dirty files and historical failure. Read 01–05 and list which can run concurrently; do not create new coding scope while collecting status.
- [ ] Collect reports and check that every diff respects existing T ownership. Route out-of-scope fixes to the owner. A report without the necessary browser or native environment remains incomplete for that acceptance item.
- [ ] After 01/02 changes are integrated and writes are paused, run `python -m unittest` from the root. Separately run the full suite with `TF2RA_PLAYWRIGHT` and `TF2RA_BROWSER` set to actual existing dependencies. Record exact test totals, failures and skips; do not install dependencies or call a skipped browser run green acceptance.
- [ ] Have 05 build the candidate against that stable snapshot. Correlate its checksum with the human reports. If 05 changes only documentation afterward, verify the relevant packaging checks and rebuild; if code changes, repeat affected checks before accepting the new build.
- [ ] Update PLAN's current state and TASKS' relevant status notes using the observed results. Preserve original task ownership and Linux-first priority; use `ready for human test` where appropriate, never `Wave 2 complete` without required native evidence.
- [ ] Add a dated current-state note to the historical UX audit and reconcile the milestone evidence. Do not rewrite its original observations as if they were made today. Explicitly distinguish adopted, completed, pending and deferred recommendations; English-only UI and private distribution are decisions, not accidental omissions.
- [ ] Write the final report: integrated source/candidate, exact tests, unresolved focus/storage defects, Linux human status, Windows human status, deferred accessibility/user study and future collaboration gate. List T6/T19 documentation requests rather than editing their files.

## Acceptance

Documents agree about the observed integrated state and candidate. No unverified Windows/microphone/Casual claim appears. Collaboration remains gated until required Linux and native Windows real-game results are recorded; a green automated suite alone does not unlock it.
