# Local UI review — 2026-10-13

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

## Validation

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
or making release claims. T19 must rebuild and publish a release only after the
remaining acceptance checks and subsequent collaboration work are complete.
