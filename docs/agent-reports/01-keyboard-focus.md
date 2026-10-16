# T15: keyboard focus after recording

Source: `b7f9f3b330d8caae743b8e1e93964c8cfea5cd0c` (uncommitted T15 changes).
Assignment: `docs/superpowers/plans/2026-10-15-local-closure/01-keyboard-focus.md`.

## Changes and cause

Saving closed the recorder, then asynchronously replaced the line list, removing
its focused trigger. The strengthened variant test observed `document.activeElement`
as BODY after the new Record again button appeared. Native dialog closure alone
cannot restore focus to a newly created control.

`tf2reaudio/web/app.js` now populates previously expanded variant details during
rendering so their controls are ready for focus immediately. After closing and
after the saved list renders, focus goes to the current variant recording button,
or the whole-line recording button when Details is closed. A filtered-out line
falls back to the class heading. Failed saves keep the modal and preview open,
re-enable Save recording, and focus that button for retry.

`tests/test_web.py` strengthens the existing variant regression and adds real UI
coverage for Escape without saving, Discard with closed Details, failed save and
successful retry of the same recording, whole-line save, and subsequent Tab.
Existing variant-only installation, fake microphone lifecycle, CSP and 200% zoom
assertions remain intact. Native close events are asynchronous: cancellation
assertions wait for the expected focus rather than adding fixed sleeps.

## Evidence

Existing dependencies only:

- Playwright 1.62.1:
  `~/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright`
- Google Chrome for Testing 156.0.8078.4:
  `~/.cache/ms-playwright/chromium-1248/chrome-linux64/chrome`

All browser commands below use those paths as `TF2RA_PLAYWRIGHT` and
`TF2RA_BROWSER`. Fixtures use temporary TF2 directories, synthetic VPK/audio,
fake microphone input and loopback servers; browser requests outside the test
server are blocked.

1. `python -m unittest tests.test_web.WebTest.test_variant_recording_and_keyboard_zoom -v`
   before strengthening: 1 test passed (2.902 s). The historical failure did not
   reproduce with its original weak assertion on this run.
2. The same command with the new assertion, before the production fix:
   1 failure (2.461 s), `Focus after variant save: <body>`.
3. `python -m unittest tests.test_web.WebTest.test_recorder_focus_cancel_failure_and_whole_line -v`
   before the production fix: 1 failure (2.314 s), focus remained on Discard.
4. Intermediate validation caught an overly broad focus selector on whole-line
   recording (null Details ancestor); it was narrowed to `.variant-row`.
   An intermediate full run reported 198 tests, 1 failure in
   `test_microphone_lifecycle_and_limit`, 2 skipped. This result was superseded
   after fixing that selector; it is not acceptance evidence.
5. `python -m unittest tests.test_web -v` after the final change:
   7 tests passed, no skips (51.967 s).
6. Final `python -m unittest` with the same Chromium environment:
   198 tests in 61.617 s, OK, 2 skipped (Windows-only data-directory test and optional real tunnel/network test).
   The ZIP duplicate-entry rejection fixture emitted its existing UserWarning.
7. `git diff --check`: passed.

## Scope and outstanding checks

Not run: native Windows, physical microphones, real TF2 playback, real RCON or
Casual reload, Firefox, screen readers, full accessibility audit and user study.
The automated zoom/keyboard checks do not establish complete WCAG acceptance.

No changes required from T14 or T16. Assignment 05 (T19) should build the private candidate
from the integrated source including these T15 changes. Assignment 06 should update status
and record its stable integrated verification; no plan/status files were edited
by this assignment.

Ruling: executed the single-agent brief in the existing shared checkout and used
this assigned report as the execution record, preserving other owners' work.
No delegation, commit, merge, publication or dependency installation performed.
At start the unrelated changes were `AUDITORIA_UX.md` and untracked
`docs/superpowers/`. During execution other owners also changed `store.py`,
`tests/test_store.py`, `docs/milestone-wave2.md` and created Linux/agent reports;
these files were not modified by this assignment. The final full-suite result
therefore describes the observed shared checkout, not an isolated T15 commit.
