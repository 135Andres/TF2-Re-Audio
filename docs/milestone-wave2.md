# Wave 2 milestone: real test on Linux and Windows

Goal: check that a WAV imported from the command line plays in TF2, measure what `apply` (`snd_restart`) does in the middle of a Casual match, and confirm RCON talks to the real game.

On Linux, run commands from the app folder with `./tf2reaudio.sh <command>`. On Windows, use `TF2ReAudio.cmd <command>` in cmd from the app folder. `python3 -m tf2reaudio <command>` also works anywhere Python is set up.

## Make a test WAV

Any recorder works if it saves **16-bit PCM, mono, 44100 Hz, 10 s or less**. Or make a 1-second beep (the `880` is the pitch; change it to get a second, different beep):

```
python3 -c "import wave,math,struct;w=wave.open('beep.wav','wb');w.setnchannels(1);w.setsampwidth(2);w.setframerate(44100);w.writeframes(b''.join(struct.pack('<h',int(12000*math.sin(2*math.pi*880*i/44100))) for i in range(44100)));w.close()"
```

On Windows, use `py -3 -c "..."` instead of `python3 -c "..."`, or run `runtime\python.exe -c "..."` if the launcher downloaded Python. You can also make the file on Linux and send `beep.wav` to your friend.

## A. Linux (you)

1. Close TF2.
2. Run `setup`. If it mentions the Phase 0 test folder, run `setup --remove-test-mod`.
3. Copy the launch options it prints. In Steam, open Library > right-click Team Fortress 2 > Properties > General > Launch Options and paste them **at the end**, keeping the options you already have.
4. Make `beep.wav` (880) and `beep2.wav` (440) with the snippet above.
5. With TF2 still closed, run `import-wav soldier/medic beep.wav`. This creates the mod folder, so TF2 mounts it at the next start.
6. Start TF2 and stay in the main menu. Run `doctor`.
   - Expected: `RCON: connected`.
   - If it says `not reachable` while TF2 is running with the launch options, record the exact redacted error and elapsed time. A roughly three-second failure does not establish missing marker echo. Diagnose launch options, port, authentication and packet behavior before requesting a T3 (`rcon.py`) change.
7. Join a Casual match as Soldier and press E (MEDIC!). Write down whether you hear the beep.
8. During the match, in a terminal: `import-wav soldier/medic beep2.wav`, then `apply`.
   - Write down whether the game stuttered and for about how long (none, under 1 s, 1–3 s, more).
   - Write down whether the sound cut out and came back.
   - Press E again and write down whether you now hear the lower beep.
9. Do step 8 once more to see if the result repeats.
10. Run `doctor --copy`. It should still say `RCON: connected` and `Changes waiting for apply: 0 files`.

## B. Windows (friend)

1. Extract the ZIP (right-click > "Extract All..."). Do the `docs/launchers.md` "Windows manual test checklist" first; it covers getting Python.
2. Open cmd in the extracted folder (type `cmd` in the Explorer address bar and press Enter).
3. `TF2ReAudio.cmd doctor`. Check that it finds TF2 and says `Voice file archive: readable`. If it doesn't find TF2, add `--tf "<your Team Fortress 2 folder>"` to every command below.
4. `TF2ReAudio.cmd setup`. Add the launch options in Steam as in A3.
5. With TF2 closed: `TF2ReAudio.cmd import-wav soldier/medic beep.wav`.
6. Start TF2. Run `TF2ReAudio.cmd doctor` and check for `RCON: connected`.
7. Join a match (or start a local map) as Soldier, press E, and write down whether you hear the beep.
8. While TF2 is running: `TF2ReAudio.cmd import-wav soldier/medic beep2.wav`, then `TF2ReAudio.cmd apply`. Write down stutter, and whether the new beep plays.

**Windows-specific risk:** files are replaced with `os.replace`. Windows refuses to replace a file another program has open, so if TF2 holds a sound file open, step 8 can fail with an error such as `Access is denied` or `The process cannot access the file because it is being used by another process`. If that happens, copy the **exact** error text, then close TF2 and run the same `import-wav` again to check it works with the game closed.

## C. What to send back

- The file from `doctor --copy` (the command prints where it saved it). It does not contain your RCON password.
- For each step above: what happened, plus the exact text of any error.
- Stutter during `apply`: yes or no, and roughly how long.
- Whether the new sound played after `apply`, or only after restarting TF2.
- Windows only: your Windows version (`winver`) and the launcher checklist results.

Do not send the output of `setup`: it contains your RCON password.

## D. Result sheet and decision

Copy this sheet for each PC. Leave an item as **Not run** until a person has
actually checked it; fixture tests do not count as real-game results.

```text
Date:
Tester:
OS and version (Windows: winver):
Python version / bundled runtime:
Browser and version (if testing the web recorder):
Candidate ZIP filename and SHA-256:

Launcher checklist: Not run / Pass / Fail
doctor finds TF2 and reads the voice archive: Not run / Pass / Fail
RCON connects to real TF2 without timeout: Not run / Pass / Fail
First imported voice plays after restarting TF2: Not run / Pass / Fail
Second voice imports while TF2 is running: Not run / Pass / Fail
apply during a real Casual match: Not run / Pass / Fail
New voice plays after apply without restarting TF2: Not run / Pass / Fail
Repeat apply gives the same result: Not run / Pass / Fail
Stutter duration and whether audio returns:
Windows file replacement while TF2 runs: Not run / Pass / Fail
If replacement failed, retry after closing TF2: Not run / Pass / Fail
Physical microphone recording, preview and Save: Not run / Pass / Fail
doctor --copy report path:
Exact error messages (remove secrets):
```

A local map can help diagnose a problem, but it does not measure Casual
mid-game behavior. Record that distinction rather than marking the Casual
item as passed.

The Wave 2 gate stays open until the required Linux and native Windows
real-game checks pass and their results are recorded. A failure needs a fix
and a repeat of the affected check. Group/sync development and automatic
apply remain gated; measuring a short interruption alone does not enable
automatic apply. Physical microphone and accessibility results are separate
from the CLI/game checks and must not be inferred from them.

## E. Linux local checks — 2026-10-15

The user wants the local Linux workflow functional before testing Windows.
Windows remains untested. The checks below advance Linux validation without
closing the real-game gate:

- Steam discovery found the installed native TF2. Its real voice archive
  contained 12,728 paths; parsing it and building the catalog took 142 ms in
  this run. The MEDIC! original for each of the nine classes was read and its
  CRC verified.
- With temporary app data and browser requests restricted to same-origin GETs,
  Chromium displayed nine class cards, 23 Soldier voice-menu lines and 1,304
  Soldier lines in All lines. It decoded an original MP3 and playback time
  advanced. Search and 200% zoom worked without JavaScript errors or horizontal
  overflow in the checked view. A screenshot was inspected.
- The Linux launcher started the normal local app at `http://127.0.0.1:8440`;
  its API reported the detected TF2 path and no pending changes or collection
  warning. It detected the old Phase 0 test mod and displayed the removal
  warning. That mod was left in place.
- After integrating T14 security headers, the full Linux suite with Chromium
  ran 179 tests, OK, 2 skipped. The six browser checks include actual inline
  script blocking and local blob-audio playback; disabling CSP makes that
  check fail. These browser tests use fake microphones and temporary TF2
  fixtures. The running local server was restarted and its new headers checked.
- A private ZIP was built twice with identical bytes and its integrity checked.
  The extracted Python entry point (`--version`, `run --help`) and Linux
  launcher (`--version`) ran successfully. This is still a local candidate.
- The extracted ZIP also passed a full local workflow using only a temporary
  fake TF2 folder and loopback fake RCON: `doctor`, `import-wav` installing
  three variants, `apply` sending `snd_restart`, and `doctor --copy` showing
  zero pending files without the fixture password. Its packaged web server
  served the UI assets, nine classes and an original preview; Restore removed
  the three installed fixture files. This proves the packaged workflow against
  fixtures, not against a running game.
- After integrating the T8 collection protections, the full Linux suite with
  Chromium ran 191 tests, OK, 2 skipped. It covers old/future collection formats,
  preserving damaged files, ZIP bounds and backup-safe cleanup. Removing each
  ZIP limit in memory makes its dedicated test fail. An additional Linux check
  confirmed that foreign files, hash-named directories and symlinks survive
  normal saves/pruning without changing their targets. Windows remains untested.

- T14 framework-error follow-up: 25 server tests pass, including strict wire
  checks for DELETE 501, HEAD 501 without a body, and oversized-header 431.
  Removing the centralized header hook makes all three cases fail. The next
  full run executed 192 tests with two skips and exposed a keyboard-focus
  failure after saving a variant recording. That failure is under investigation;
  the current integration is not yet a clean full-suite result.

The real-installation checks installed no recordings and sent no RCON commands
to the real game. Physical
microphone recording, hearing replacements in the game and `apply` during
Casual still need real-use results. Browser playback progress is evidence of
decoding, not a human listening test.

## F. Linux physical microphone session

Use [the Linux session record](linux-real-session-2026-10-15.md) to record
observations. Run this procedure in a normal desktop browser with a physical
input. Do not enable fake microphone flags or select an output monitor.

1. Keep TF2 closed for the first recording. Open `http://127.0.0.1:8440`
   after starting `./tf2reaudio.sh run`. Choose Start solo if prompted.
2. Open Setup & settings. Export collection if there are existing takes.
   Record any existing Soldier MEDIC! selection and variant overrides so they
   can be restored. Remove the old experimental mod with Remove
   tf2reaudio_test if shown; it can mask the replacement being tested.
   This removes the experimental folder, so preserve it first if wanted.
3. Choose Soldier > Start with MEDIC! and record the whole command, rather
   than a single variant. Select the physical microphone. Allow microphone
   access for this local page. Record the browser version and input name.
4. Use Test microphone and speak. Record whether the level moves. Choose
   Start recording, say a distinctive phrase such as "Linux Medic take one",
   and Stop after 2–3 seconds. Confirm the browser microphone indicator stops.
5. Play the preview and listen with headphones. Record whether the phrase is
   audible and intelligible. Try Retake, then Discard; confirm the microphone
   stops and no take was saved. Reopen, record the phrase and Save recording.
   Record any silence/clipping warning and the affected variant filenames.
6. Reopen and start a short recording, then press Escape. Confirm capture
   stops. Reopen and let recording reach 10 seconds; confirm it stops itself.
   Discard that recording. The saved short phrase should remain selected.
7. In Setup & settings, copy the launch options into Steam, preserving any
   existing options. These contain a password: do not paste them in the result
   sheet. Start TF2 after saving, so the new mod folder is mounted.
8. Run `./tf2reaudio.sh doctor --copy`. Record RCON status and elapsed command
   time. A timeout is a failure requiring diagnosis; its cause is not proven
   merely by taking about three seconds.
9. As Soldier, press E in a local map or Casual. Record the exact context and
   whether you hear the distinctive phrase. A local map result does not pass
   the Casual check.
10. During an actual Casual match, record and save "Linux Medic take two" in
    the app. Click Apply changes to TF2 (the button includes a change count).
    Record time from click to completion separately from the perceived game
    freeze and audio interruption. Press E and listen for take two. Repeat
    with a third distinguishable take. Never infer heard audio from an apply
    acknowledgement or from zero pending files.
11. Run `./tf2reaudio.sh doctor --copy` again and preserve its report. In the
    result sheet record each attempt, stutter estimate, audio recovery, exact
    errors with secrets removed, and whether restarting TF2 was needed.
12. Restore the previous selection from History, or choose Restore original
    for this collection if it had no custom take. Restore any changed variant
    selections separately. Apply or restart TF2 and listen again to verify
    cleanup. Keep recordings in History unless you explicitly want deletion.

If permission is blocked, record the message, allow it in the browser's site
settings, and retry. If capture fails or is silent, check the selected physical
input and OS mute state. Record both the failure and retry; do not overwrite
one with the other. This session does not validate Firefox unless repeated
there, native Windows, full accessibility, or automatic apply.

## G. Integrated checkpoint — 2026-10-15

The historical 192-test focus failure in section E and the Linux preparation
record is superseded by the coordinator's current run: `python -m unittest`
ran 198 tests, OK, 9 skipped. With existing Playwright and Chromium enabled,
the same suite ran 198 tests, OK, 2 skipped; all seven browser checks ran.
The skips are the Windows-only data-directory test and the optional real
network/tunnel test. Packaging tests: 2 passed, no skips. These are fixture
results, not physical microphone or real-game acceptance.

[Report 05](agent-reports/05-private-candidate.md) identifies the frozen private
candidate `dist/TF2ReAudio-0.1.0.zip`, SHA-256
`60c105c1631860e1e516bd524282fd552c9f3a7ffac22b6a6c0fdd954d01ff33`.
Coordination independently checked its archive integrity and implementation
bytes. T19 reports repeat-build equality and an extracted fixture workflow.
The archive contains the guide before this coordinator update: use this current
guide alongside it, including the corrected timeout diagnosis in A6. T19 owns
rebuilding with updated packaged guidance and supplying a new checksum.
Source is HEAD `b7f9f3b330d8caae743b8e1e93964c8cfea5cd0c` plus uncommitted
T8/T15 fixes; it is not a clean release commit.

| Acceptance item | Current evidence | Result |
|---|---|---|
| Linux automated local workflow and recorder focus | Coordinator suite; reports 01/02 | Pass with fixtures |
| Private candidate packaging | Report 05; coordinator archive and packaging checks | Pass for the frozen archive |
| Linux physical microphone and real TF2/RCON/Casual | Linux session sheet; no assigned 03 report supplied | Not run |
| Native Windows, bootstrap, locking, microphone and real game | [Prepared Windows sheet](agent-reports/04-windows-validation.md) | Not run |
| Full accessibility and five-person study | No new human results | Not run |

Keep the Linux session and Windows outcome sheets private alongside the ZIP;
the builder currently omits those sheets and agent reports. Their links are
source-checkout references, not files included in the frozen archive. T19 must
resolve the offline-document handoff; T6 owns the obsolete stub expectations
in `docs/launchers.md`. No application fix is requested from T3/T9 without
observed real-game evidence. Wave 2 stays open. Collaboration, automatic apply
and publication are not authorized by these automated results. See the
[coordinator report](agent-reports/06-integration-status.md) for owner requests.
