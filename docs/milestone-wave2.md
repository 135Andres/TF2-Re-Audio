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
   - If it says `not reachable` while TF2 is running with the launch options, and the command took about 3 seconds, write that down. It means TF2 does not answer RCON's end-of-output marker (the echo concern in TASKS.md, Wave 2 milestone), and `rcon.py` must change.
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
