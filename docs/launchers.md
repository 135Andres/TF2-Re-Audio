# Launchers

| File | System | What it runs |
|---|---|---|
| `TF2ReAudio.cmd` | Windows 10/11 (64-bit) | `<python> -m tf2reaudio run` (no args) or `<python> -m tf2reaudio <args>` |
| `tf2reaudio.sh` | Linux | `python3 -m tf2reaudio run` (no args) or `python3 -m tf2reaudio <args>` |

Both work from a double-click or a terminal, use their own folder as the working folder (so they work from anywhere, including paths with spaces), and pass any extra arguments through. If something fails, they print what to do and wait for a key before the window closes.

## Windows: how Python is found

1. `py -3`, then `python`, then `runtime\python.exe` next to the launcher. Each is **run** (not just looked up) with a check that it is Python 3.10 or newer **and** can import `tf2reaudio` from the launcher folder. Running it skips the Microsoft Store `python` alias, which exits with an error when given arguments. Its stdin is `nul`, so a "do you want to install Python?" prompt cannot hang the launcher.
2. If none works, it downloads the official **Windows embeddable package** from python.org (no installer, no admin, no winget):
   - Downloads with `curl.exe` (built into Windows 10 1803+). Falls back to PowerShell `Invoke-WebRequest`.
   - Checks the SHA-256 pinned in the script with PowerShell `Get-FileHash`. On mismatch it deletes the file and stops.
   - Unpacks to `runtime\` with `Expand-Archive`, then deletes the ZIP.
   - Appends `..` to `runtime\python312._pth`. The embeddable Python ignores `PYTHONPATH` and the current folder and only searches the folders in that file, resolved relative to `runtime\`. So `..` is the launcher folder. (This `._pth` behaviour was checked on Linux with Python 3.14's `getpath`, which is the same code Windows uses.)
3. Later runs reuse `runtime\` without downloading again. To force a fresh download, delete `runtime\`.

### Pinned runtime

- Version: **Python 3.12.10**, `python-3.12.10-embed-amd64.zip`, 11,133,606 bytes. This is the last 3.12 release with Windows binaries; later 3.12.x releases are source-only.
- SHA-256: `4acbed6dd1c744b0376e3b1cf57ce906f9dc9e95e68824584c8099a63025a3c3`
- Where the hash comes from: python.org does not publish a SHA-256 for this file. The hash was computed on 2026-10-11 from the download, after two checks:
  - Its MD5 matched the one python.org publishes (`fe8ef205f2e9c3ba44d0cf9954e1abd3`, from `/api/v2/downloads/release_file/?release=1007`).
  - Its GPG signature (`.zip.asc`) checked as valid from **Steve Dower (Python Release Signing)**, key fingerprint `7ED1 0B65 31D7 C8E1 BC29 6021 FC62 4643 4870 34E5`.
- To update: change `PY_VERSION` and `PY_SHA256` in `TF2ReAudio.cmd`, check the new file the same way, then run the Windows checklist below. If you move to 3.13 or later, `python3*._pth` already matches the new file name.

### Not in the embeddable package (and not needed)

The embeddable package has no `tkinter`, `pip`, `venv`/`ensurepip` or IDLE. TF2 Re-Audio needs none of them:
- It uses only the standard library (AGENTS.md).
- The UI runs in the browser. Even "Choose another folder" is a path field checked by the API (TASKS T15), not a `tkinter` dialog.

Modules the app does rely on are included: `ssl`, `sqlite3`, `ctypes`, `socket`, `hashlib`, `zipfile`, `json`, `http.server`, `urllib`, `webbrowser`, `winreg`.

## Linux

- Uses `python3` if it is 3.10 or newer.
- If `python3` is missing or too old, it prints an install command based on `ID` and `ID_LIKE` in `/etc/os-release`:
  - Arch and Arch-based: `sudo pacman -S python`
  - Debian, Ubuntu, Mint: `sudo apt install python3`
  - Fedora, RHEL, Nobara: `sudo dnf install python3`
  - Anything else: a generic message.
- **Double-click:** if neither stdin nor stdout is a terminal and a display is available, it reopens itself in the first terminal it finds: `x-terminal-emulator`, `gnome-terminal`, `konsole`, `xfce4-terminal` or `xterm`. That window waits for Enter after an error. Some file managers open `.sh` files in a text editor instead. In that case use "Run" / "Execute", or run it from a terminal.
- The file must stay executable. It is marked `+x` in git, and the release ZIP (T19) must keep that mode.

### Tested on Linux (Arch, KDE, Python 3.14)

- From another folder, from a folder with spaces, `(`, `)` and `&` in its name: it runs `python3 -m tf2reaudio run <args>` in the launcher folder and forwards arguments exactly.
- No `python3`, and a fake `python3` 3.8: correct message and install hint.
- The `/etc/os-release` cases listed above, plus a missing file.
- Launcher copied alone, without the `tf2reaudio` folder: "Extract the whole ZIP first".
- No terminal with a display set: it reopened in a real `konsole` with the path passed correctly, and waited for Enter on error.
- `bash --posix`, plus `shellcheck` reports no issues.

## Windows manual test checklist

Nobody has run `TF2ReAudio.cmd` on Windows yet. Please do these tests, write down the result of each one, and send screenshots of anything unexpected.

Until `run` is implemented, a "good" result ends with `Not implemented yet`, then `TF2 Re-Audio stopped with error code 1`, then `Press any key to continue . . .`. Once `run` exists, a good result is the browser opening TF2 Re-Audio instead.

**Preparation**
- Extract the release ZIP with right-click > "Extract All...". You get a folder containing `TF2ReAudio.cmd` and `tf2reaudio\`.
- If Windows shows "Windows protected your PC", click "More info" > "Run anyway". Write down whether this appeared.
- To check which Python a test used, look in the folder: `runtime\` exists only if the launcher downloaded Python.

**A. Fresh PC without Python** (or Windows Sandbox / a new VM). On a fresh Windows, `python` is the Microsoft Store alias, so this also covers that case.
1. In cmd, `where python` should show `...\AppData\Local\Microsoft\WindowsApps\python.exe` or nothing. Write down which.
2. Double-click `TF2ReAudio.cmd`.
   - Expected: "Python 3.10 or newer was not found", a curl download progress bar, then "Python 3.12.10 is ready", then the good result.
   - The Microsoft Store must **not** open.
3. Check: `runtime\python.exe` exists, `runtime-download.zip` is gone, and the last line of `runtime\python312._pth` is `..`.
4. Double-click again. Expected: no download, straight to the good result.

**B. Only the Store alias, PC with the `py` launcher removed.** If A already showed the WindowsApps alias, A covers this. Otherwise: Settings > Apps > Advanced app settings > App execution aliases > turn **on** "python.exe" and "python3.exe" (App Installer). Delete `runtime\`, then repeat A2.

**C. PC with Python 3.12 installed** (from python.org, with the `py` launcher).
1. Delete `runtime\` if it exists, then double-click. Expected: the good result, no download, and no `runtime\` folder is created.
2. If you also have an older Python (3.9 or lower) as `python`, the result should be the same, because `py -3` picks the newest.

**D. Path with spaces and symbols.** Move the whole folder to `C:\Users\<you>\Desktop\TF2 Re Audio (test) & co\`. Delete `runtime\`. Repeat A2 and A4 (double-click), then E.

**E. From a terminal**, with the folder from D:
1. cmd: `cd /d C:\` then `"C:\Users\<you>\Desktop\TF2 Re Audio (test) & co\TF2ReAudio.cmd"`. Expected: the good result. The window must not close, and the prompt returns after a key.
2. PowerShell: `cd ~` then `& "C:\Users\<you>\Desktop\TF2 Re Audio (test) & co\TF2ReAudio.cmd"`. Expected: the same.
3. cmd: `TF2ReAudio.cmd --help` from inside the folder. Expected: the help text of `tf2reaudio`, which shows that arguments are forwarded.
4. After a run, `echo %ERRORLEVEL%` in cmd should print the app's exit code (1 for the stub).

**F. Error cases**
1. *Not extracted:* open the ZIP in Explorer without extracting and double-click `TF2ReAudio.cmd` inside it. Expected: "The "tf2reaudio" folder was not found ... Extract the whole ZIP first", then a pause.
2. *Offline:* delete `runtime\`, disconnect from the internet, and double-click. Expected: "curl.exe failed, trying PowerShell instead...", then "Could not download Python from python.org", then a pause. Reconnect, run again, and it should work.
3. *Bad hash:* copy `TF2ReAudio.cmd` to `Test.cmd`. In Notepad, change the last character of `PY_SHA256`. Delete `runtime\` and run `Test.cmd`. Expected: "The downloaded Python file is corrupted ... It was deleted", no `runtime\` folder, and no `runtime-download.zip`. Delete `Test.cmd` afterwards.
4. *Folder you cannot write to:* if possible, put the folder in `C:\Program Files\` (as a normal user) and delete `runtime\`. Expected: a clear error ("Could not unpack" or curl's write error) and a pause, not a silent close.

**Send back:** your Windows version (`winver`), the result of each step, whether SmartScreen appeared, and screenshots of anything unexpected.

## Failure codes

Every launcher failure starts with a code in brackets. Testers send the code and the last step they saw; a screenshot helps if personal folder names are hidden. The launcher never writes log files, because setup output can contain passwords.

| Code | Meaning |
|---|---|
| `BOOT_FOLDER` | The launcher's own folder could not be opened. |
| `BOOT_NOT_EXTRACTED` | The ZIP was not fully extracted. |
| `BOOT_PYTHON_MISSING` | Linux: Python 3.10+ is missing. (Windows downloads it instead.) |
| `BOOT_DOWNLOAD` | Windows: downloading Python failed. |
| `BOOT_HASH` | Windows: the downloaded Python did not match the pinned SHA-256. |
| `BOOT_EXTRACT` | Windows: Python could not be unpacked (folder not writable). |
| `BOOT_IMPORT` | Windows: Python was unpacked but could not import the app. |
| `BOOT_APP_EXIT` | Python started and the app exited with an error. Run `doctor --bundle` for a diagnostic ZIP. |

Once Python works, `doctor --bundle` saves a shareable diagnostic ZIP under the data folder's `reports` folder (the newest three are kept) even when TF2 is missing. Errors before Python starts, and Python syntax or import failures before diagnostics start, are not recorded automatically.

## Known limits

- Windows: only 64-bit (amd64). Windows on ARM should run it through emulation, but nobody has tested that. 32-bit Windows is not supported.
- Ctrl+C in the Windows console asks "Terminate batch job (Y/N)?". This is normal `cmd` behaviour.
- Linux: if `python3` points to Python 3.9 or older while a newer `python3.X` is also installed, the launcher does not look for it. It asks you to update instead.
