# TF2 Re-Audio — private local-test candidate

Private candidate for local review; no public release is available.

Record custom TF2 voices on your computer. This candidate supports solo use;
group sharing is still pending. Windows, real microphones, and the effect of
reloading sounds during a real TF2 match still need human testing. See
[the validation report](docs/local-ui-review.md) and
[the Linux/Windows checklist](docs/milestone-wave2.md).

## Start

1. Extract the ZIP into a writable folder; do not run it inside the ZIP viewer.
2. On Windows 10/11 (64 bit), double-click `TF2ReAudio.cmd`. It uses Python 3.10
   or newer, or downloads the official Python runtime with its pinned checksum.
   On Linux, run `./tf2reaudio.sh`; if needed, first run `chmod +x tf2reaudio.sh`.
3. Keep the launcher window open. The app opens locally in your browser.
4. If TF2 is not detected, enter your **Team Fortress 2** folder, or its `tf`
   subfolder. The app validates the folder before saving it.
5. Choose Soldier, then **Start with MEDIC!**. Test or select your microphone,
   click **Start recording**, then **Stop** (the limit is 10 seconds).
6. Listen, optionally disable silence trimming, and **Save recording**.
   The recorder shows which game files it will replace. Your microphone stops
   when you stop recording or close the recorder, including with Escape.
7. Restart TF2 once after the mod folder is first created. Press E as Soldier
   to check your voice. Subsequent changes can use **Apply**, if RCON is set up.

Only your PC's local files are used while the game plays audio. Recording and
backups work without a group account. Browser microphone permission is needed.

## Optional TF2 connection

Open **Setup & settings**, check the RCON port, and click **Copy launch options**.
In Steam → Team Fortress 2 → Properties → General, add these at the end of
**Launch Options**, keeping your existing options. If copying is unavailable,
select and copy the text shown in the app. Restart TF2 and click **Check
connection**. If TF2 is closed or connection fails, your recordings remain saved;
close and reopen TF2 to load the installed files. An apply request does not
prove that the new voice was heard in the game.

## Recover a voice and make backups

- **Play original** only previews the original; it does not change your selection.
- **Use original on my PC only** overrides a line locally. Switch back with
  **Use collection voice on my PC**.
- **Restore original for this collection** changes that line's selection.
  **Undo last change** restores the previous selection. Sharing is not enabled.
- **History** lets you listen before selecting an older recording. If imported
  collections conflict, both recordings remain available; select one in History
  to resolve the conflict.
- **Details & variants** lists technical filenames and supports recording or
  restoring individual variants. Variant edits remain separate from whole-line
  edits; restore an edited variant separately if you want all originals.
- **Setup & settings → Export collection** downloads a backup ZIP.
  **Import collection ZIP** merges a backup with the existing collection.

## Update

Close the app, extract the new program ZIP, and launch the new version.
Your recordings live outside the program folder and survive replacing it.
Back up your collection before an update.

## Disable or uninstall

In **Setup & settings**:

1. **Disable voices** moves the mod out of TF2 without deleting recordings.
   Use **Enable voices** to bring it back. Restart TF2 to unload or load it.
2. **Delete collection** permanently removes local recordings and the installed
   mod. Export a backup first. The app asks before deleting anything.
3. **Uninstall** removes the mod, optionally deletes the collection, and shows
   the exact launch options to remove from Steam. Keep all your other options.
   Close the app and delete its program folder. To remove remaining local data,
   delete `%APPDATA%\TF2ReAudio` on Windows or `$XDG_DATA_HOME/tf2reaudio` on Linux
   (normally `~/.local/share/tf2reaudio`). Restart TF2 to unload the mod.

## If something fails

Keep the launcher window open and retry. Allow microphone access for the local
page in your browser. If TF2 is not writable or locks sound files, close TF2 and
retry. **Setup & settings** can remove the old `tf2reaudio_test` experimental mod.

From the extracted folder, run `TF2ReAudio.cmd doctor --copy` on Windows or
`./tf2reaudio.sh doctor --copy` on Linux. The report omits RCON passwords and
other secrets. See [launcher troubleshooting](docs/launchers.md). Do not send
your copied launch options to others: they contain the local RCON password.
