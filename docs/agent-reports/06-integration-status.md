# 06 — Integration and project status

Date: 2026-10-15. Status: integrated automated checks pass; Linux local workflow ready for human testing. Wave 2 remains open.

## Scope and source identity

Started with the distribution README and local-closure README; followed assignment 06. Updated only `PLAN.md`, `TASKS.md`, `AUDITORIA_UX.md`, `docs/milestone-wave2.md`, and this report. All document writes use `util.atomic_write`. Preserved the pre-existing audit note and Linux microphone procedure. No application/test changes, staging, commits, merges, downloads, publication or delegation were performed.

Source HEAD: `b7f9f3b330d8caae743b8e1e93964c8cfea5cd0c`. Initial tracked dirty files:

```text
AUDITORIA_UX.md
docs/README.md
docs/local-ui-review.md
docs/milestone-wave2.md
tests/test_store.py
tests/test_web.py
tf2reaudio/store.py
tf2reaudio/web/app.js
```

Initial untracked paths: `docs/agent-reports/`, `docs/linux-real-session-2026-10-15.md`, `docs/superpowers/`. PLAN/TASKS and this report are additional coordinator changes. T19's report appeared during evidence collection and was consumed before the status update. No implementation changes were observed between snapshot measurements.

Implementation/test snapshot SHA-256 before and after integrated testing:
`63339da3cb3adc0b6e78348b49cef4390ec49d1514bd56835f47fe84bab09e7a`.
Computed from SHA-256 per file, keyed by relative POSIX path, for sorted non-cache files under `tf2reaudio/` plus sorted `tests/test_*.py`, then SHA-256 of `json.dumps(mapping, sort_keys=True).encode()`. This is an auxiliary identity; report 05's per-input manifest identifies the packaged bytes.

## Evidence collected and ownership review

| Assignment | Evidence | Coordinator conclusion |
|---|---|---|
| 01 / T15 | `01-keyboard-focus.md`; app.js and test_web.py diff | Ownership respected. Focus restoration after rerender, cancellation and retry covered by current browser suite |
| 02 / T8 | `02-storage-recovery.md`; store.py and test_store.py diff | Ownership respected. Module errors replace raw persistence OSError; injected backup/primary/local/blob failures pass |
| 03 / human Linux | Assigned report absent; `docs/linux-real-session-2026-10-15.md` available | Preparation only. Historical focus failure superseded; physical microphone and real game still Not run |
| 04 / human Windows | `04-windows-validation.md` | Checklist prepared; native results Not run |
| 05 / T19 | `05-private-candidate.md`; README and local-review diff; existing archive | Ownership respected. Frozen private candidate identified; reproduced/extracted checks attributed to T19 |

01/02 could implement independently; 03/04 could prepare evidence sheets in parallel. Final testing/packaging consumes settled 01/02 implementation. No further coding scope was opened. The plain and Chromium coordinator suites overlapped briefly in this shared checkout; both use isolated temporary fixtures. No production files were written by those tests, and implementation hashes stayed unchanged. The integrated results below replace historical 192-test/one-focus-failure status, not historical observations themselves.

## Verification observed by coordination

Environment: Linux, Python 3.14.8. Existing dependencies only.

1. `python -m unittest`: **198 tests in 20.139 s, OK, 9 skipped**. Seven browser tests skipped without configuration; one Windows-only data-directory test and one optional real network/tunnel test skipped.
2. Full configured suite:

   ```sh
   TF2RA_PLAYWRIGHT=~/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright \
   TF2RA_BROWSER=~/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome \
   python -m unittest
   ```

   **198 tests in 49.601 s, OK, 2 skipped**: Windows-only data-directory and optional real network/tunnel. All seven browser checks ran, including variant-save focus, cancellation, failed-save retry, microphone lifecycle/10-second limit, CSP/blob playback and limited keyboard/200% zoom coverage. Fake microphones, synthetic TF2/VPK/audio and loopback fake servers only. The deliberate duplicate ZIP-entry fixture emits its existing UserWarning.
3. `python -m unittest tests.test_build_zip -v`: **2 tests in 0.008 s, OK, no skips**.
4. Archive inspection with stdlib `hashlib`/`zipfile`: SHA-256 matches report 05; `testzip()` returns None; 35 entries. All packaged implementation bytes match current source. Every packaged input digest matches report 05's recorded manifest. After coordinator edits, the only packaged-source mismatch is `docs/milestone-wave2.md`.
5. `git diff --check`: passed after status edits. A separate final document review checks UTF-8/LF, local links and required status/identity fields; no new implementation tests were added for these documentation changes.

No failing test or unresolved focus/storage defect remains established by these runs. Their scope does not prove physical durability, full accessibility or real-game behavior.

## Candidate and current documentation

Frozen candidate: `dist/TF2ReAudio-0.1.0.zip`, 79,252 bytes.
SHA-256: `60c105c1631860e1e516bd524282fd552c9f3a7ffac22b6a6c0fdd954d01ff33`.

T19 reports two identical builds, exclusions, portable modes and extracted import/apply/restore/web smoke with fixtures. Coordination independently verified archive integrity, manifest correspondence and implementation bytes; it did not repeat T19's extracted smoke or rebuild their output. The candidate and human reports have no completed real-game result to correlate: the Linux record used the source checkout without a ZIP hash; Windows has no tester/candidate result.

The frozen ZIP predates this coordinator's milestone update. Its implementation is the tested implementation; its guide retains the old A6 timeout diagnosis and lacks section G. Current source guidance is an explicit supplement. Keep the frozen checksum/history intact; T19 should regenerate after the owner requests below, then record the new identity. No clean-commit, final-release or human-acceptance claim is made.

## Gate decision and owner requests

- **03 / Linux human validation:** create the assigned report `docs/agent-reports/03-linux-validation.md` and record physical microphone, real RCON/playback, repeated actual Casual apply, interruptions and restoration against the identified candidate. Existing preparation does not pass any of these checks.
- **04 / Windows human validation:** after Linux acceptance, run the prepared native checklist with a recorded candidate checksum. Bootstrap, locking/replacement, microphone and actual Casual behavior remain Not run.
- **T6 — docs/launchers.md:** replace obsolete stub/code-1 and prompt-return expectations (lines 61, 85, 88 in the inspected guide) with current UI startup and controlled exit checks. Keep implementation unchanged without evidence of a launcher defect.
- **T19 — docs/local-ui-review.md and report/build handoff:** correct the descriptions of the two configured skips: Windows-only data-directory plus optional real network/tunnel, rather than two network checks. Preserve report 05 as historical evidence and identify a superseding candidate explicitly.
- **T19 — tools/build_zip.py / docs/README.md / offline guidance:** supply the Linux session and prepared Windows sheet alongside the private ZIP, or explicitly scope packaging changes. The existing packaged milestone F links to an omitted Linux record; new source guidance also references omitted agent reports. Avoid broken offline links without broadly including work orders or secrets. Regenerate the candidate after the coordinator's milestone edits and T6/T19 documentation updates; rerun packaging/extraction checks and record a new checksum. No builder change is made under coordination ownership.
- **T0/T8:** simulated ENOSPC at os.replace is covered; physical power loss, actual disk exhaustion, short writes and flush/fsync failures remain Not run. No specific atomic_write defect or additional implementation fix is established.
- **T3/T9:** no code change requested without real-game evidence. Corrected milestone A6 so elapsed timeout alone no longer diagnoses missing marker echo.

Full Firefox, screen-reader/WCAG and five-person study acceptance remain pending. Collaboration T11→T12→T13→T18 remains gated by required Linux/native Windows results. Automatic apply remains disabled pending its own decision. Private distribution, English-only UI and deferred publication/license decisions remain intact.

## Execution record and review

Ruling: execute this documentation-only, explicitly single-agent assignment in the existing shared checkout and use this report as the ledger; do not create a branch/worktree, delegate, commit or modify other owners' files. This preserves the integrated dirty snapshot. Cost if wrong: concurrent writes could invalidate identity; pre/post implementation hashes and archive comparisons were checked.

Ruling: preserve the already identified T19 artifact rather than overwrite another owner's output after changing the packaged milestone. Record the exact documentation delta and route regeneration to T19 as the brief requires. Cost if wrong: a tester could follow stale instructions; current guidance and the A6 correction are explicitly supplied as a supplement.

Completed: baseline/scope review, available report collection, integrated suites, frozen candidate verification, project-status reconciliation, historical-audit follow-up and owner-specific handoff. Human acceptance and T19's superseding documentation build are pending dependencies, not completed checks. Final review: self-review under the assignment's no-delegation rule; no independent reviewer was dispatched. Deferred minors: none newly identified; documentation handoff requests above remain open.
