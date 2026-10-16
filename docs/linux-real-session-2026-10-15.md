# Linux real-use session — 2026-10-15

Status: preparation complete; physical microphone and real-game acceptance pending.

## Build and environment

- Source HEAD at preflight: `b7f9f3b330d8caae743b8e1e93964c8cfea5cd0c`.
  Other work modified store/web files during this session. Results below
  describe the observed runs, not a frozen clean candidate; rerun acceptance
  after those changes settle.
- App: 0.1.0; Python: 3.14.8.
- OS: Linux 7.2.9-arch1-1, x86_64, glibc 2.44.
- Test browser: bundled Chromium revision 1248. Human browser/version: Not recorded.
- Candidate: source checkout, not an extracted ZIP; ZIP hash: Not applicable.
- Tester for physical checks: Not recorded.

## Observed preflight results

| Check | Result | Evidence |
|---|---|---|
| Native Steam installation detected | Pass | One installation; install check OK |
| Real voice archive readable | Pass | 12,728 archive entries; 8,916 logical lines |
| TF2 running at preflight | No | No TF2 process observed |
| RCON ready | Not configured | `doctor` and `/api/state` agree |
| Replacement mod exists | No | `custom/tf2reaudio` not created yet |
| Experimental mod | Present | `custom/tf2reaudio_test`; remove before playback checks |
| Pending files | 0 | `doctor` and `/api/state` |
| Physical input available to OS | Detected, not capture-tested | Built-in Audio Analog Stereo; default source `alsa_input.pci-0000_00_1f.3.analog-stereo`; mute: no |
| Local Linux launcher | Pass | Started `./tf2reaudio.sh run --no-browser` |
| Local service responds | Pass | `http://127.0.0.1:8440/api/ping` and `/api/state` |

Doctor report: `~/.local/share/tf2reaudio/doctor-report.txt`.
This is a preflight snapshot; `doctor --copy` overwrites that path. Preserve a
separate copy before collecting a later report if both are needed.

## Automated checks

- `python3 -m unittest`: 192 tests, OK, 8 skipped. Six optional browser
  checks and two real-network checks were skipped. Fixtures do not access
  the physical microphone or real TF2.
- Browser-only run with the existing Playwright package and Chromium:
  6 tests, 5 passed, 1 failed. `test_variant_recording_and_keyboard_zoom`
  failed with `Focus after variant save: <body>`. This reproduces the known
  T15 focus issue. The other checks, including fake microphone lifecycle,
  passed. These are not physical-input acceptance results.
- No new code tests were added for this documentation-only preparation.

## Human result sheet

Follow [the physical microphone procedure](milestone-wave2.md#f-linux-physical-microphone-session).
Enter Pass or Fail only after direct observation; preserve failed attempts.

| Check | Result | Observation / exact error |
|---|---|---|
| Experimental mod removed before listening | Not run | |
| Physical microphone selected; meter reacts to speech | Not run | |
| 2–3 second recording and intelligible preview | Not run | |
| Retake and Discard preserve previous selection | Not run | |
| Save installs the whole MEDIC! command | Not run | |
| Stop, Discard and Escape release microphone | Not run | |
| Recording stops at 10 seconds | Not run | |
| RCON connects to real TF2 without timeout | Not run | |
| First phrase audible after TF2 restart | Not run | Context: local map / Casual |
| Second phrase saved while TF2 runs | Not run | |
| First apply during actual Casual | Not run | |
| Second phrase audible without TF2 restart | Not run | |
| Repeat apply during actual Casual | Not run | |
| Third phrase audible without TF2 restart | Not run | |
| Final doctor report: connected, 0 pending | Not run | |
| Previous voice/original restored and heard | Not run | |

| Casual attempt | Distinct phrase | Command elapsed time | Perceived freeze | Audio interruption / recovery | New phrase heard? | Restart needed? |
|---|---|---|---|---|---|---|
| 1 | | Not measured | Not observed | Not observed | Not run | Not recorded |
| 2 | | Not measured | Not observed | Not observed | Not run | Not recorded |

Record stutter as none, under 1 s, 1–3 s, or over 3 s unless a more precise
measurement exists. Command latency and game stutter are separate observations.

## Limits and handoffs

No real microphone capture, take installation, experimental-mod removal,
Steam launch-option edit, real-game playback or `snd_restart` was performed
in this preparation. No microphone quality or game behavior is inferred from
OS device detection. Windows and Firefox remain untested; full accessibility
and extracted-candidate acceptance remain pending. Wave 2 stays open and
automatic apply/group work remain gated.

T15 needs to repair focus restoration after saving a variant and rerun its
browser acceptance check. No implementation files owned by other tasks were
changed. T3/T9 changes are not yet requested: real RCON and playback evidence
is needed before diagnosing a game integration fault.
