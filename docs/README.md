# TF2 Re-Audio

Give your favorite TF2 classes your own voice. Record a line, listen, and try it in the game.
No account needed. Your recordings stay on your computer.

## Start

1. Extract the whole ZIP into a folder.
2. **Windows 10/11 (64-bit):** double-click `TF2ReAudio.cmd`.
   **Linux:** open a terminal in that folder and run `sh tf2reaudio.sh`.
3. The app opens in your browser. Keep the launcher window open.

You'll need TF2 installed, a microphone, and a browser with microphone support.
Windows downloads Python if needed on the first launch. Linux needs Python 3.10 or newer.

## Your first recording

1. Choose **Start solo**. If TF2 isn't found, enter your **Team Fortress 2** folder.
2. Pick **Soldier** → **Start with MEDIC!**. Allow microphone access when asked.
3. Click **Start recording**, then **Stop**. Listen and click **Save recording**.
4. Restart TF2, play as Soldier, and press **E**.

Want the original voices back? In **Setup & settings**, choose **Disable voices**,
then restart TF2. Your recordings stay saved. Use **Enable voices** to bring them back.

## More help

<details>
<summary><strong>Try changes without restarting TF2</strong></summary>

Restart TF2 once after your first recording. After that, you can set up the optional connection:

1. Open **Setup & settings** → **Copy launch options**.
2. In Steam, open **Team Fortress 2 → Properties → General → Launch Options**.
   Add the copied text at the end, keeping your existing options.
3. Restart TF2 and click **Check connection** in the app.
4. Use **Apply changes** after saving new recordings, then listen in TF2.

Keep these launch options private: they include your local connection password.
You can also keep using the app without this connection and restart TF2 to load changes.

</details>

<details>
<summary><strong>Restore a voice or save a backup</strong></summary>

Open **More: history, undo, variants** on a voice line to find its restore options.
**Use original on my PC only** switches that line back to TF2's voice.
Choose **Use collection voice on my PC** to return to your recording.
**History** lets you listen to older recordings and choose one.
If you edited individual variants, restore those separately too.

In **Setup & settings**, use **Export collection** to save a backup ZIP.
Use **Import collection ZIP** to bring recordings back; it merges them with your current collection.

</details>

<details>
<summary><strong>Update or uninstall</strong></summary>

**Update:** export a backup, close the app, extract the new program ZIP into a new folder,
and launch it. Recordings are stored separately from the program folder.

**Uninstall:** open **Setup & settings → Uninstall** and follow the steps shown.
Keep a backup of recordings you want to save. Only select **Also delete my local collection**
if you want to permanently delete your recordings. Close the app and delete its program folder.

Data is stored in `%APPDATA%\TF2ReAudio` on Windows, or
`$XDG_DATA_HOME/tf2reaudio` on Linux (usually `~/.local/share/tf2reaudio`).

</details>

<details>
<summary><strong>Something isn't working?</strong></summary>

- **No microphone?** Allow microphone access in your browser and check the selected input.
- **TF2 wasn't found?** Enter the **Team Fortress 2** folder or its `tf` subfolder in **Setup & settings**.
- **Voice hasn't changed?** Close and reopen TF2. If the app couldn't write a sound file, close TF2 and try **Apply changes** again.
- **App won't open?** Check that the whole ZIP was extracted and keep the launcher window open to read its message.

For a help report, open a terminal in the program folder and run:

- **Windows:** `TF2ReAudio.cmd doctor --copy`
- **Linux:** `sh tf2reaudio.sh doctor --copy`

The report leaves out passwords and tokens.
See [launcher help](https://github.com/135Andres/TF2-Re-Audio/blob/main/docs/launchers.md)
or [report an issue](https://github.com/135Andres/TF2-Re-Audio/issues).

</details>

This early version supports solo use. Group sharing is planned. Voices have been tested
in TF2 on Linux; Windows testing is still pending.
