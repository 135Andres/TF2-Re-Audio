# Public release packaging — 2026-10-16

The user explicitly authorized publishing GitHub releases on 2026-10-16,
superseding the historical private-distribution restriction below. Version
0.1.0 is published as an early preview, with the existing Windows and
real-network acceptance limits retained.

## Changes and validation

- The release ZIP now includes LICENSE, NOTICE, the sharing guide and the
  Windows checklist. Packaged README links work independently of their location
  in the source tree. The repository README points to the installable release ZIP.
- Added a regression test that first failed on the missing LICENSE. It checks
  the extracted notices/guides, local README links and CLI startup from a path
  containing spaces, including the Linux launcher from a different directory.
- `python -m unittest tests.test_build_zip -v`: 3 tests passed.
- `python -m unittest`: 250 tests, OK, 18 skipped (16 optional browser checks
  and two optional external-network checks). The existing duplicate-ZIP-entry
  rejection fixture emits a UserWarning.
- Against a freshly extracted ZIP, with temporary data, copied test fixtures,
  and package import location verified: CLI, server and sync integration suites,
  46 tests passed. No real TF2 or external network was used by these tests.
- Separate Chromium run: 16 checks, 15 passed and
  `test_group_host_generates_local_join_link` failed. Its mocked tunnel origin
  `https://friends.example` is rejected by the existing host allowlist introduced
  in the security hardening commit. A diagnostic rerun changing only that fake
  origin in memory to `https://friends.trycloudflare.com` passed. The original
  browser test file was not changed because it belongs to T15.
- The publication procedure builds twice and checks byte equality, uploads the
  ZIP and SHA-256 checksum to a draft release, downloads them for comparison,
  then publishes the preview and verifies the public asset bytes.

## Limits and owner handoff

Native Windows startup/runtime download, physical microphones, real TF2/Casual,
real tunnels and real-network sharing were not tested in this release session.
The preview status does not complete those acceptance milestones.

T15 needs to update the mocked origin and expected invitation URL in
`tests/test_web.py::WebTest.test_group_host_generates_local_join_link` to a fake
allowed Quick Tunnel origin. No production module changes are requested.
Historical reports below describe their original candidates, not this release.

---

# Local UI review — private candidate, 2026-10-15

This is an implementation and fixture-validation report, not a Windows or
real-game acceptance sign-off. The starting suite had 160 tests, with two
network tests skipped. Existing uncommitted work was preserved.

## Completed work (T14–T17)

- Closing the recorder with Escape, its close button, or Discard releases its
  microphone tracks, cancels visual updates, and releases preview URLs. Late
  permission results also stop their tracks. Recording ends through a timer
  independent of animation frames, with a safe fallback when no limit callback
  is supplied. Save uses the validated WAV directly.
- The local HTTP server denies framing with `X-Frame-Options: DENY` on normal
  API/static responses and errors. On Windows it disables address reuse so an
  occupied listening port can trigger the existing fallback. POST `KeyError`
  failures now return a clear 400 response instead of exposing a bare key as
  a 500. A nonexistent recording already returned a readable 400 before this
  change; the pasted review was too broad about that case.
- Lines now expose Play original, preview the selected recording, local
  original override, collection restore, Undo, and History with audio previews
  and version selection. Imported conflicts are visible and can be resolved
  from History without dropping either recording.
- Details lists variant filenames and supports recording, restoration, local
  override, and history per variant. The API reports inherited selections;
  progress counts logical commands, including commands with edited variants.
  Variant edits remain independent of whole-line selections.
- Start with MEDIC!, Continue recording, Next line, Pending only, search, and
  all four categories are available. All lines includes every category.
  Nine original SVG class emblems are bundled with letter fallbacks.
- Settings supports RCON port edits, copied or manually selected launch options,
  checking connection, applying after a restart, removing the experimental test
  mod, export/import ZIP backups, disable/enable, collection deletion, and guided
  uninstall. The uninstall flow removes the mod and optionally the collection;
  it explains the manual removal of Steam options, the program folder, and
  remaining app data. Destructive collection actions require confirmation.
- Restart reminders are visible and can be acknowledged. Acknowledgement only
  dismisses the reminder; it does not claim RCON connectivity, successful apply,
  or playback. Sharing and automatic apply remain unavailable pending their
  planned milestones.
- User-facing strings are centralized in `strings.js`. The changed JS is
  formatted for review. Tabs support arrow/Home/End keys, status changes use
  live regions, keyboard focus returns to the changed line, and detail rendering
  is deferred until expanded.

## Historical validation (2026-10-13)

- `python -m unittest`: standard-library suite; optional browser checks are
  skipped unless their environment is configured. Tests use temporary fake TF2
  folders and loopback servers with OS-assigned ports. They do not access a
  real TF2 installation, real RCON, Steam, or the external network.
- Full run with the existing local Playwright package and Chromium enabled:
  **173 tests, OK, 2 skipped** (the real tunnel/network tests). Linux, Python 3.14,
  Chromium (Chrome for Testing 156.0.8078.4). No package installation or browser download was needed.
- Browser invocation on Linux:

  ```sh
  TF2RA_PLAYWRIGHT=/path/to/existing/playwright/package \
  TF2RA_BROWSER=/path/to/existing/chromium \
  python -m unittest tests.test_web -v
  ```

- The five browser checks exercise Escape, late microphone permission,
  permission denial, the 10-second stop without animation frames, WAV saving,
  restore/Undo/local override, listening controls and history selection,
  conflict resolution preserving both takes, export/delete/import, cancelled
  deletion, disable/enable/uninstall, RCON port and launch options, test-mod
  removal, restart acknowledgement, wrong-folder recovery, single-variant
  installation, keyboard tabs, and CSS zoom at 200% without horizontal overflow.
- Dashboard and class/settings screenshots were inspected in Chromium, including
  the 200% zoom layout. This is a limited visual and keyboard check, not full
  WCAG 2.2 AA certification.
- Server tests cover frame headers, expected errors, variant inheritance and
  progress, restart acknowledgement, occupied-port fallback, and single-instance
  behavior. Instance messages are captured instead of polluting suite output.

## Current private candidate validation (2026-10-15)

The candidate uses source commit `b7f9f3b330d8caae743b8e1e93964c8cfea5cd0c`
plus the current uncommitted T8 storage recovery and T15 recorder focus changes.
The exact final ZIP checksum and source identity are recorded separately in
`docs/agent-reports/05-private-candidate.md` in the source checkout; that report
is deliberately not packaged, avoiding a self-referential archive checksum.

Fresh Linux checks with Python 3.14.8:

- `python -m unittest`: 198 tests, OK, 9 skipped (seven optional browser checks
  and two optional real tunnel/network checks).
- With existing Playwright and Chromium configured, `python -m unittest`:
  198 tests, OK, 2 skipped (the real tunnel/network checks). All seven browser
  checks ran, including variant-save focus and failed-save retry. The deliberate
  duplicate-entry ZIP rejection fixture emits its existing UserWarning.
- `python -m unittest tests.test_build_zip -v`: 2 tests, OK, no skips.
- Extracted candidate: `python -m tf2reaudio --version`,
  `python -m tf2reaudio run --help`, and the Linux launcher's `--version`
  passed from a path containing spaces. The launcher also ran from a different
  working directory. Python's ZIP extractor does not restore executable bits;
  the smoke check restored the archived mode, as described by the README's
  `chmod +x` fallback.
- An isolated extracted-process check used temporary data, a synthetic VPK/WAV,
  disabled Steam discovery and fake loopback RCON on an OS-assigned port.
  Import installed all three MEDIC! variants; apply sent `snd_restart` to the
  fake server; `doctor --copy` reported connected without exposing its fixture
  password; restoring ORIGINAL removed the installed files. A temporary local
  web server served the page, six JS/CSS resources and `/api/ping` successfully.
  No real TF2, physical microphone or external service was used.

The final archive is rebuilt after documentation changes. T19's separate report
records byte equality of two final builds, archive integrity, exact source-byte
comparison, packaged local assets, launcher permissions and secret/data exclusions.
This is a private testing candidate. No upload, public release, license selection
or human acceptance is implied.

## Candidate packaging (T19)

`python tools/build_zip.py` builds `dist/TF2ReAudio-0.1.0.zip` atomically and prints
its SHA-256. The ZIP includes the package, local web assets, both launchers,
README, launcher guide, milestone checklist, and this report. Source selection
excludes user data, secrets, caches, downloaded runtimes, and unrelated files.
Archive paths and permissions are portable; the Linux launcher retains its
executable bit. Tests verify reproducibility, exclusions, archive integrity,
and preservation of the previous candidate when a required file is missing.
The extracted candidate was checked with `--version` and `run --help`.

## Not tested; remaining acceptance work

- Native Windows socket behavior, locking, launcher runtime download, file
  replacement, and browser microphone permissions. The address-reuse policy
  is covered by the code/test; the actual Windows behavior is unverified.
- Physical microphones, other browsers, a screen reader, full keyboard-only
  navigation through every feature, and the five-person accessibility study.
- Real TF2/RCON, whether the voice plays in Casual, or the duration of a
  `snd_restart` interruption. The candidate is not a production release.
- Group identity, invitations, synchronization, hosting, and real tunnels remain
  T11–T13/T18 work after the Windows/real-game milestone.

## Changes needed from other tasks

No changes to T0–T13 modules are required by these local UI changes. Human
Windows and TF2 validation remains required before proceeding to collaboration
or making release claims. T19 must rebuild the final candidate after the
remaining acceptance checks.
Publication remains deferred until the user explicitly authorizes it.
