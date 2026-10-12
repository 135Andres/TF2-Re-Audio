#!/usr/bin/env python3
"""TF2 Re-Audio - Phase 0 test kit.

Replaces every class's "MEDIC!" call (E key) with a beep sound, so you can check
whether custom voice lines play on Casual and whether snd_restart reloads them.

  python3 phase0_test.py install   # write the test sounds (do this with TF2 CLOSED the first time)
  python3 phase0_test.py play      # ask the running game to play Soldier's MEDIC! (works in the main menu)
  python3 phase0_test.py restart   # ask the running game to run snd_restart
  python3 phase0_test.py remove    # delete the test sounds
"""
import math, os, pathlib, platform, re, secrets, shutil, socket, struct, subprocess, sys, tempfile, wave

MOD = "tf2reaudio_test"
CLASSES = ["scout", "soldier", "pyro", "demoman", "heavy", "engineer", "medic", "sniper", "spy"]
WAV_IN_MP3_CLASS = "scout"  # gets raw WAV bytes named .mp3, to learn if real MP3 encoding is required
RCON_PORT = 27015
HERE = pathlib.Path(__file__).resolve().parent


def find_tf_dir():
    if platform.system() == "Windows":
        roots = [pathlib.Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam"]
    else:
        home = pathlib.Path.home()
        roots = [home / ".local/share/Steam", home / ".steam/steam",
                 home / ".var/app/com.valvesoftware.Steam/.local/share/Steam"]
    libs = []
    for root in roots:
        vdf = root / "steamapps/libraryfolders.vdf"
        if vdf.exists():
            libs += [pathlib.Path(p.replace("\\\\", "\\")) for p in re.findall(r'"path"\s+"([^"]+)"', vdf.read_text(errors="replace"))]
        libs.append(root)
    for lib in libs:
        tf = lib / "steamapps/common/Team Fortress 2/tf"
        if (tf / "tf2_sound_vo_english_dir.vpk").exists():
            return tf
    sys.exit("Could not find Team Fortress 2. Is it installed through Steam?")


def vpk_files(path):
    """Yield every file path stored in a VPK directory file (v1/v2)."""
    with open(path, "rb") as f:
        sig, ver, _ = struct.unpack("<III", f.read(12))
        assert sig == 0x55AA1234, "not a VPK file"
        if ver == 2:
            f.read(16)

        def cstr():
            b = bytearray()
            while (c := f.read(1)) != b"\0":
                b += c
            return b.decode()

        while ext := cstr():
            while d := cstr():
                while name := cstr():
                    preload = struct.unpack("<IHHIIH", f.read(18))[1]
                    f.read(preload)
                    yield f"{d}/{name}.{ext}"


def beep_wav(path):
    """Three rising square-wave beeps: impossible to confuse with a real voice line."""
    rate, frames = 44100, bytearray()
    for freq in (660, 880, 1320):
        for i in range(int(rate * 0.15)):
            frames += struct.pack("<h", 9000 if math.sin(2 * math.pi * freq * i / rate) > 0 else -9000)
        frames += b"\0\0" * int(rate * 0.05)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(frames)


def to_mp3(wav, mp3):
    # shortcut: needs ffmpeg or lame on PATH, fine for this one-off test; the real app must encode without them.
    if shutil.which("ffmpeg"):
        cmd = ["ffmpeg", "-loglevel", "error", "-y", "-i", str(wav), "-ac", "1", "-ar", "44100", "-b:a", "128k", str(mp3)]
    elif shutil.which("lame"):
        cmd = ["lame", "--quiet", "-m", "m", "-b", "128", str(wav), str(mp3)]
    else:
        sys.exit("Need ffmpeg or lame installed to build the test MP3.")
    subprocess.run(cmd, check=True)


def rcon_password():
    f = HERE / "rcon_password.txt"
    if not f.exists():
        f.write_text(secrets.token_hex(8))
    return f.read_text().strip()


def launch_options():
    return f"-usercon +ip 127.0.0.1 +hostport {RCON_PORT} +rcon_password {rcon_password()} +net_start"


def rcon(command):
    def packet(req_id, kind, body):
        data = struct.pack("<ii", req_id, kind) + body.encode() + b"\0\0"
        return struct.pack("<i", len(data)) + data

    def read(s):
        size = struct.unpack("<i", s.recv(4))[0]
        data = b""
        while len(data) < size:
            data += s.recv(size - len(data))
        return struct.unpack("<ii", data[:8])

    try:
        s = socket.create_connection(("127.0.0.1", RCON_PORT), timeout=3)
    except OSError:
        sys.exit("TF2 is not reachable over RCON. Is the game running with these launch options?\n  " + launch_options())
    with s:
        s.sendall(packet(1, 3, rcon_password()))
        while True:  # server sends an empty response value before the auth response
            req_id, kind = read(s)
            if kind == 2:
                break
        if req_id == -1:
            sys.exit("RCON password rejected. Copy the launch options again:\n  " + launch_options())
        s.sendall(packet(2, 2, command))
    print(f"Sent to TF2: {command}")


def install():
    tf = find_tf_dir()
    lines = [p for p in vpk_files(tf / "tf2_sound_vo_english_dir.vpk")
             if re.fullmatch(r"sound/vo/(%s)_medic\d+\.mp3" % "|".join(CLASSES), p)]
    out = tf / "custom" / MOD
    with tempfile.TemporaryDirectory() as tmp:
        wav, mp3 = pathlib.Path(tmp, "beep.wav"), pathlib.Path(tmp, "beep.mp3")
        beep_wav(wav)
        to_mp3(wav, mp3)
        for p in lines:
            dest = out / p
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(wav if pathlib.Path(p).name.startswith(WAV_IN_MP3_CLASS + "_") else mp3, dest)
    print(f"Installed {len(lines)} test files into {out}")
    print("\nSet these TF2 launch options in Steam (right click TF2 > Properties > Launch Options):\n  " + launch_options())


def remove():
    out = find_tf_dir() / "custom" / MOD
    if out.exists():
        shutil.rmtree(out)
    print(f"Removed {out}")


if __name__ == "__main__":
    actions = {"install": install, "remove": remove,
               "restart": lambda: rcon("snd_restart"),
               "play": lambda: rcon("play vo/soldier_medic01.mp3")}
    if len(sys.argv) != 2 or sys.argv[1] not in actions:
        sys.exit(__doc__)
    actions[sys.argv[1]]()
