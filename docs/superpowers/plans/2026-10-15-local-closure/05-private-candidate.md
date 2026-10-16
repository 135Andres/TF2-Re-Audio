# T19: reproducible private candidate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task when available. Steps use checkbox (`- [ ]`) syntax for tracking. This is a single-agent assignment; do not delegate additional work.

**Goal:** Build and describe a private candidate from a stable integrated source snapshot for Linux and later Windows testing.

**Architecture:** Reuse build_zip and its existing exclusions, reproducible metadata and atomic output. Refresh the candidate report to reflect current evidence and limitations.

**Tech Stack:** Python >=3.10 standard library, unittest, local HTML/CSS/JavaScript; existing optional Chromium/Playwright only where specified.

**Spec:** `TASKS.md` T19; `PLAN.md` private distribution decision and local acceptance criteria.

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

Modify only `tools/build_zip.py`, `tests/test_build_zip.py`, `docs/README.md`, and `docs/local-ui-review.md`. Create `docs/agent-reports/05-private-candidate.md`. Generated candidate ZIPs under `dist/` are permitted outputs, not files to commit/publish.

Consume 01/02's integrated revisions and 06's test baseline. Preserve `build_zip(root: Path = ROOT, output: Path | None = None) -> tuple[Path, str]`. Do not change launchers or application modules. Do not package the agent work orders or reports, test secrets or local settings through a broad include rule.

## Review Focus

- A code change is made after building: checksums and source identity must identify the tested build.
- Two builds from identical input differ: investigate reproducibility before handing off.
- A fixture password/user data leaks into the ZIP: retain explicit exclusions.
- Extracted entry points or local UI assets are missing: validate the archive, not only the source checkout.
- Old documentation says all tests pass or implies Windows approval: update only to current evidence.

## Steps

- [ ] Review T19 implementation and `tests/test_build_zip.py`; run `python -m unittest tests.test_build_zip -v`. Do not rewrite working packaging just to create a code change.
- [ ] Update the English README and local review to distinguish implemented features, observed checks and untested real-game/Windows behavior. Replace obsolete completion claims with the actual integrated result or a clearly pending item. Keep human gate and private status explicit.
- [ ] Wait for 01/02 integration and a stable source snapshot coordinated with 06. Record commit, relevant dirty files and Python version; do not build during concurrent source/document writes.
- [ ] Run `python tools/build_zip.py` twice without changing any packaged inputs. Capture both printed SHA-256 values and verify byte equality using a saved first build in a temporary directory via atomic_write. Check `zipfile.ZipFile.testzip()` returns None, expected assets exist, executable metadata for `tf2reaudio.sh` is preserved, and secrets/data/runtimes/caches are absent.
- [ ] Extract into a temporary folder. Check `python -m tf2reaudio --version`, `python -m tf2reaudio run --help` and the Linux launcher's `--version` there. Use temporary app data and fake TF2/RCON only for an extracted smoke test covering import, apply and restore, with no real-game discovery/network side effects. Reuse existing fixture helpers; do not add a permanent test that accesses real TF2.
- [ ] Write the source identity, SHA-256, exact commands/results, extraction checks and native Windows/physical mic/TF2 limitations in the new report. If packaged documentation changes afterward, rebuild and replace the reported checksum before handoff.
- [ ] Hand the candidate path/checksum to 03/04/06. Do not upload, publish, tag a release or select a license.

## Acceptance

Two identical-input builds are byte-identical; archive integrity, exclusions and extracted entry points pass. The report identifies the exact private candidate and does not imply human acceptance.
