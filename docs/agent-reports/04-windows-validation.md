# 04 — Native Windows validation

Preparation date: 2026-10-15.
Status: checklist prepared; native Windows execution **Not run**.

This is the evidence sheet for assignment 04. Follow the adapted instructions
below alongside [the launcher guide](../launchers.md) and
[Wave 2 B–D](../milestone-wave2.md#b-windows-friend). No Windows results have
been supplied or observed in this session. Linux inspection is not native
Windows acceptance.

## Source and readiness

- Inspected source HEAD: `b7f9f3b330d8caae743b8e1e93964c8cfea5cd0c`.
- Host used for preparation: Linux; Python 3.14.8.
- Tracked dirty files observed before this report: `AUDITORIA_UX.md`,
  `docs/milestone-wave2.md`, `tests/test_store.py`, `tests/test_web.py`,
  `tf2reaudio/store.py`, `tf2reaudio/web/app.js`.
- Untracked paths observed: `docs/agent-reports/`,
  `docs/linux-real-session-2026-10-15.md`, `docs/superpowers/`.
- Assignment 05 candidate identity/checksum: Pending; no 05 report available.
- Assignment 03/06 stable Linux acceptance handoff: Pending; neither report
  available. The existing Linux session document records human checks as
  Not run and a historical browser focus failure; this session did not rerun it.
- Native Windows tester/environment: Not recorded.

Preparation may proceed now. Start native acceptance only after the Linux
stability handoff and an identified private candidate from 05/06. Do not use
an arbitrary ZIP under `dist/` as evidence of that handoff. Keep the ZIP and
this sheet private. Repeat affected checks after fixes against the new candidate.

## Session identity — complete before execution

| Field | Value |
|---|---|
| Actual test date and timezone | Not recorded |
| Tester | Not recorded |
| Windows edition/version/build (`winver`) | Not recorded |
| System type (Settings > System > About; x64 required) | Not recorded |
| Native Windows host / VM | Not recorded |
| Source commit and included dirty changes from 05/06 | Pending |
| Candidate ZIP filename | Pending |
| Expected SHA-256 from 05 | Pending |
| Observed SHA-256 on Windows | Not recorded |
| Extraction path | Not recorded |
| Python version and selected command/runtime | Not recorded |
| Browser and version | Not recorded |
| Physical microphone name and Windows input/mute state | Not recorded |
| Steam/TF2 version and selected TF2 folder | Not recorded |
| Previous MEDIC! selection, variant overrides and backup location | Not recorded |

In PowerShell, run `Get-FileHash -Algorithm SHA256 -LiteralPath
'C:\path\TF2ReAudio-0.1.0.zip'` on one line. Compare with the expected hash
before testing. Use separate sheets for different Windows versions, browsers,
or candidate hashes. A native Windows VM can cover launcher checks; it does
not establish physical microphone or real Casual behavior unless actually tested.

## Launcher checklist — adapted expectations

Success for a normal launch means the local browser UI opens and responds.
`Not implemented yet` is obsolete and must not count as success. The app
normally keeps its console running while it serves the UI; a prompt need not
return until it stops. A successful `--version` or `--help` should exit with
code 0. In cmd, run `echo %ERRORLEVEL%` immediately after that command.
Errors must remain readable with the launcher's pause; record their exact text.

Use disposable folders/VMs for missing-runtime and failure cases. Do not
uninstall Python, change primary aliases, or delete an existing user's runtime
to manufacture a case. Record an unavailable scenario as Not run with a reason.
Close the app before moving a test folder or repeating a fresh-runtime case.

| ID | Procedure and expected observation | Result | Evidence / exact error |
|---|---|---|---|
| W01 | Extract the whole candidate ZIP with Extract All; launcher and package are adjacent | Not run | |
| W02 | Record SmartScreen/Defender/firewall messages, including whether none appeared | Not run | |
| W03 | On a fresh native Windows test environment with no supported Python, record `where py` and `where python`; double-click launcher: pinned runtime download, verified extraction, local UI opens | Not run | |
| W04 | Store-alias-only environment without `py`: same result; Store must not open or hang | Not run | |
| W05 | After download, `runtime\python.exe` exists, `runtime-download.zip` is gone, `python312._pth` includes `..`; record `runtime\python.exe --version` | Not run | |
| W06 | Repeat launch with bundled runtime: UI opens without another download | Not run | |
| W07 | Separate environment with supported Python: UI opens without downloading/creating runtime; record `py -3 --version` / `python --version` as applicable | Not run | |
| W08 | Supported `py -3` plus older PATH Python: supported interpreter is selected | Not run | |
| W09 | Extract to `Desktop\TF2 Re Audio (test) & co`; repeat fresh-runtime and reuse launches | Not run | |
| W10 | From another cmd directory, invoke quoted full launcher path; UI opens | Not run | |
| W11 | From another PowerShell directory, use `& "C:\full path\TF2ReAudio.cmd"`; UI opens | Not run | |
| W12 | Run `TF2ReAudio.cmd --help` and `--version` from cmd; arguments forwarded; each exit code is 0 | Not run | |
| W13 | Open launcher from unextracted ZIP: readable Extract the whole ZIP error and pause | Not run | |
| W14 | Disposable environment without any usable Python/runtime, offline: readable download failure and pause; reconnect and retry successfully | Not run | |
| W15 | Disposable extracted copy: copy launcher to Test.cmd, change one PY_SHA256 character, ensure no usable system Python/runtime; hash rejection deletes download, installs no runtime; remove test copy afterward | Not run | |
| W16 | Disposable non-writable folder, normal user, no usable Python/runtime: readable write/unpack error and pause | Not run | |

An existing `runtime` directory alone does not prove which interpreter was
selected: the launcher tries `py -3`, then `python`, then its runtime. Record
the available commands and setup for each case. Preserve unexpected failures;
do not disable security software to make a check pass.

## Real TF2 and physical microphone procedure

1. With TF2 closed, start the extracted app. Export any existing collection
   from Setup & settings. Record the current Soldier MEDIC! selection and
   variant overrides. If the experimental `tf2reaudio_test` mod is present,
   preserve it if wanted and use the existing removal action before listening.
2. In cmd in the extracted folder, run `TF2ReAudio.cmd doctor --copy`.
   Record detected TF2, voice archive readability and report location. If
   discovery fails, append `--tf "C:\path\Team Fortress 2"` to each game
   command (including `run`) and record automatic and manual-path results
   separately. `doctor --copy` overwrites its report; preserve each snapshot.
3. Run `TF2ReAudio.cmd setup`. Append its launch options in Steam while
   preserving existing options. They contain a password: never attach the
   output, launch options, or settings.json to this report.
4. Follow Wave 2's WAV requirements: PCM16 mono, 44100 Hz, at most 10 s.
   Prepare two distinguishable WAVs, `beep.wav` and `beep2.wav`. Its generation
   snippet uses `py -3` on Windows, or `runtime\python.exe` if bundled Python
   is the available interpreter. Import with TF2 closed:
   `TF2ReAudio.cmd import-wav soldier/medic "beep.wav"`.
5. Start TF2 so the new mod folder is mounted. Run
   `TF2ReAudio.cmd doctor --copy`; record connected status, elapsed command
   time and any exact error. A timeout needs diagnosis; duration alone does
   not prove that the empty RCON marker caused it.
6. As Soldier press E. Listen and record whether the first beep is heard,
   and whether this was a local map or actual Casual.
7. During actual Casual, run
   `TF2ReAudio.cmd import-wav soldier/medic "beep2.wav"`, then
   `TF2ReAudio.cmd apply`. Record import and apply separately. Press E and
   listen for the second beep without restarting TF2. Repeat using a distinct
   third take or the first beep. Record command duration separately from game
   freeze and audio interruption/recovery on both attempts.
8. If replacement fails, preserve the exact redacted message and the failed
   attempt. Close TF2 and retry the same import. Record whether it succeeds
   and whether a restart makes it audible. A closed-game retry does not pass
   live replacement. Do not diagnose a Windows lock without evidence.
9. In a normal desktop browser select a physical microphone, allow access,
   and test the level meter. Record a distinctive 2–3 second phrase, stop,
   listen to preview and Save the whole Soldier MEDIC! command. Check Retake,
   Discard, Escape and the 10-second limit; verify the microphone indicator
   stops after capture/closing. Record any permission denial and its retry.
   Do not enable fake microphone flags. Record save, preview and heard in-game
   playback as separate observations. Repeat per browser being claimed.
10. Collect a final `doctor --copy` report. Restore the previous command and
    variant selections from History, or restore original if previously unused.
    Apply or restart and listen to verify cleanup. Keep history unless deletion
    is explicitly wanted; do not delete the user's data directory.

| ID | Actual-use check | Result | Observation / exact redacted error |
|---|---|---|---|
| G01 | TF2 auto-discovery and voice archive readable | Not run | |
| G02 | Manual --tf fallback if needed | Not run | |
| G03 | Backup/previous selection recorded; interfering test mod handled | Not run | |
| G04 | First WAV imported with TF2 closed | Not run | |
| G05 | Real TF2 RCON connected without timeout | Not run | |
| G06 | First voice heard after TF2 restart | Not run | Context: Not recorded |
| G07 | Second WAV replaces files while TF2 is running | Not run | |
| G08 | First apply during actual Casual | Not run | |
| G09 | Second voice heard without TF2 restart | Not run | |
| G10 | Repeated import/apply during actual Casual | Not run | |
| G11 | Repeated voice heard without restart; audio returns | Not run | |
| G12 | On replacement failure, same import retried with TF2 closed | Not run | |
| G13 | Final doctor: connected and zero pending files | Not run | |
| M01 | Physical mic selected; meter responds to speech | Not run | |
| M02 | Short recording, intelligible preview and Save | Not run | |
| M03 | Retake/Discard preserve selection; Stop/Escape release mic | Not run | |
| M04 | Automatic stop at 10 seconds releases mic | Not run | |
| M05 | Permission denial/recovery if exercised | Not run | |
| M06 | Saved physical recording heard in TF2 | Not run | Context: Not recorded |
| G14 | Previous voice/original and variant choices restored and heard | Not run | |

| Casual attempt | Candidate / take | Import result | Apply elapsed | Game freeze | Audio interruption / recovery | New voice heard | Restart needed |
|---|---|---|---|---|---|---|---|
| 1 | Not recorded | Not run | Not measured | Not observed | Not observed | Not run | Not recorded |
| 2 | Not recorded | Not run | Not measured | Not observed | Not observed | Not run | Not recorded |

For freeze estimates use none, under 1 s, 1–3 s or over 3 s unless measured
more precisely. Attach before/after doctor reports and redacted errors with
step IDs and timestamps. Keep failed attempts and append retries. Successful
apply acknowledgements, zero pending files and local maps do not prove a new
voice was heard in Casual. Required failures remain open until fixed/retested.

## Preparation verification observed now

- `python --version`: Python 3.14.8 on the Linux preparation host.
- `python -m tf2reaudio run --help`, `import-wav --help`, `doctor --help`,
  `apply --help`: all exited 0. Confirmed current commands and --tf syntax.
  Help parsing did not launch the server or touch the real game.
- Compared the checklist against the actual launcher, CLI parser, existing
  milestone and assignment 04. No application code or existing guides changed.
- Report validation: 36 native outcome rows are all Not run; both local
  document links resolve; source identity and pending checksum are recorded;
  the file reads as UTF-8/LF. `git diff --check` exited 0.
- Final status also shows external changes in `docs/README.md` and
  `docs/local-ui-review.md`; this assignment did not modify them. The shared
  checkout is changing, so its HEAD is not a frozen candidate identity.
- No unittest suite was run for this documentation-only change; no new code
  tests were added. No native Windows, download, network, physical microphone,
  live file replacement, real RCON or Casual test was executed.

## Handoff to 06 and owner requests

- **06 (integration/status):** preparation delivered; execution pending Linux
  stability, candidate identity and a native tester. Keep Wave 2 open. Record
  supplied results against this sheet; do not infer Pass from fixtures.
- **T6 — docs/launchers.md:** replace obsolete Not implemented yet/code-1
  success expectations and prompt-return assumptions with the current running
  local UI and exit-code-0 checks. Runtime presence alone does not identify
  the chosen Python. Keep launcher implementation unchanged pending evidence.
- **05/T19 — candidate report/build packaging:** supply the frozen candidate
  filename, SHA-256 and source identity after Linux stabilizes. The current
  build allowlist does not include this report; provide it privately alongside
  the ZIP, or let T19 explicitly package it if desired.
- **06 — docs/milestone-wave2.md A6:** a roughly three-second RCON failure
  alone does not establish missing marker echo; request diagnosis before
  prescribing a T3 change.
- **T1 steam.py / T3 rcon.py / T9 game.py and T0 util.py / T16 recorder.js /
  T14 server.py:** no implementation fix requested without native evidence.
  Route discovery, timeout/auth, locked-file/atomic-write, microphone and local
  server failures to the respective owner with step ID, candidate hash and
  exact redacted error. Do not edit those modules under this assignment.

Full accessibility, additional browser/Windows coverage and the five-user
study remain untested. This report does not authorize automatic apply,
group/sync development, publication or a release.
